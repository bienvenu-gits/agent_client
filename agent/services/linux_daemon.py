"""
Daemon Linux (systemd) pour l'agent d'inventaire

Ce module implémente un daemon Linux compatible systemd
pour l'agent d'inventaire.
"""

import os
import sys
import subprocess
import signal
import time
from typing import Dict, Any
from pathlib import Path

from .base_service import BaseService


class LinuxSystemdService(BaseService):
    """
    Gestionnaire de service systemd pour l'agent d'inventaire

    Cette classe implémente l'interface BaseService pour Linux
    et gère les services systemd.
    """

    def __init__(self):
        """
        Initialise le gestionnaire de service systemd
        """
        super().__init__(
            service_name="watchman-agent-client",
            display_name="Watchman Agent Client",
            description="Watchman system monitoring and surveillance service"
        )

        # Chemins systemd
        self.service_file = f"/etc/systemd/system/{self.service_name}.service"
        self.user_service_file = f"{os.path.expanduser('~')}/.config/systemd/user/{self.service_name}.service"

        # Déterminer si on utilise les services système ou utilisateur
        self.use_user_service = os.geteuid() != 0  # Non-root utilise user service

    def _get_systemctl_cmd(self) -> list:
        """
        Retourne la commande systemctl appropriée

        Returns:
            list: Commande systemctl avec les bons paramètres
        """
        if self.use_user_service:
            return ['systemctl', '--user']
        else:
            return ['systemctl']

    def _get_service_file_content(self) -> str:
        """
        Génère le contenu du fichier service systemd

        Returns:
            str: Contenu du fichier .service
        """
        # Déterminer le chemin vers l'exécutable Python et le script
        python_executable = sys.executable
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")

        # Utilisateur et groupe pour le service
        if self.use_user_service:
            user_config = ""  # Les services utilisateur n'ont pas besoin de User/Group
        else:
            user_config = f"""User=watchman-agent-client
Group=watchman-agent-client"""

        # Répertoires de travail et configuration
        if self.use_user_service:
            working_dir = os.path.expanduser("~/.local/share/watchman-agent-client")
            config_dir = os.path.expanduser("~/.config/watchman-agent-client")
        else:
            working_dir = "/var/lib/watchman-agent-client"
            config_dir = "/etc/watchman-agent-client"

        service_content = f"""[Unit]
Description={self.description}
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
ExecStart={python_executable} {script_path} --mode service --config {config_dir}/config.ini
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier={self.service_name}
WorkingDirectory={working_dir}
{user_config}

# Sécurité
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths={working_dir} {config_dir}
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictRealtime=yes

# Limites de ressources
LimitNOFILE=65536
TasksMax=100

[Install]
WantedBy={'default.target' if self.use_user_service else 'multi-user.target'}
"""
        return service_content

    def install(self) -> bool:
        """
        Installe le service systemd

        Returns:
            bool: True si l'installation a réussi
        """
        try:
            # Déterminer le fichier service à utiliser
            service_file = self.user_service_file if self.use_user_service else self.service_file

            # Créer les répertoires nécessaires
            os.makedirs(os.path.dirname(service_file), exist_ok=True)

            # Si c'est un service système, créer l'utilisateur dédié
            if not self.use_user_service:
                self._create_service_user()

            # Créer les répertoires de données
            self._create_service_directories()

            # Écrire le fichier service
            with open(service_file, 'w') as f:
                f.write(self._get_service_file_content())

            print(f"✅ Fichier service créé: {service_file}")

            # Recharger systemd
            cmd = self._get_systemctl_cmd() + ['daemon-reload']
            subprocess.run(cmd, check=True, capture_output=True)

            # Activer le service au démarrage
            cmd = self._get_systemctl_cmd() + ['enable', self.service_name]
            subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Service '{self.service_name}' installé et activé")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur commande systemd: {e}")
            print(f"Sortie d'erreur: {e.stderr.decode()}")
            return False

        except Exception as e:
            print(f"❌ Erreur installation service: {e}")
            return False

    def uninstall(self) -> bool:
        """
        Désinstalle le service systemd

        Returns:
            bool: True si la désinstallation a réussi
        """
        try:
            # Arrêter le service s'il tourne
            if self.is_running():
                self.stop_service()

            # Désactiver le service
            try:
                cmd = self._get_systemctl_cmd() + ['disable', self.service_name]
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError:
                pass  # Service peut ne pas être activé

            # Supprimer le fichier service
            service_file = self.user_service_file if self.use_user_service else self.service_file

            if os.path.exists(service_file):
                os.remove(service_file)
                print(f"✅ Fichier service supprimé: {service_file}")

            # Recharger systemd
            cmd = self._get_systemctl_cmd() + ['daemon-reload']
            subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Service '{self.service_name}' désinstallé")
            return True

        except Exception as e:
            print(f"❌ Erreur désinstallation service: {e}")
            return False

    def start_service(self) -> bool:
        """
        Démarre le service systemd

        Returns:
            bool: True si le démarrage a réussi
        """
        try:
            cmd = self._get_systemctl_cmd() + ['start', self.service_name]
            subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Service '{self.service_name}' démarré")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur démarrage service: {e}")
            if e.stderr:
                print(f"Erreur: {e.stderr.decode()}")
            return False

    def stop_service(self) -> bool:
        """
        Arrête le service systemd

        Returns:
            bool: True si l'arrêt a réussi
        """
        try:
            cmd = self._get_systemctl_cmd() + ['stop', self.service_name]
            subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Service '{self.service_name}' arrêté")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur arrêt service: {e}")
            return False

    def restart_service(self) -> bool:
        """
        Redémarre le service systemd

        Returns:
            bool: True si le redémarrage a réussi
        """
        try:
            cmd = self._get_systemctl_cmd() + ['restart', self.service_name]
            subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Service '{self.service_name}' redémarré")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur redémarrage service: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du service systemd

        Returns:
            dict: Statut détaillé du service
        """
        try:
            # Vérifier le statut avec systemctl
            cmd = self._get_systemctl_cmd() + ['status', self.service_name, '--no-pager']
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Parser la sortie de systemctl status
            status_info = {
                'installed': self.is_installed(),
                'enabled': False,
                'active': False,
                'running': False,
                'failed': False,
                'exit_code': result.returncode
            }

            if result.stdout:
                status_text = result.stdout.lower()

                # Vérifier les différents états
                if 'enabled' in status_text:
                    status_info['enabled'] = True

                if 'active (running)' in status_text:
                    status_info['active'] = True
                    status_info['running'] = True
                elif 'active' in status_text:
                    status_info['active'] = True

                if 'failed' in status_text:
                    status_info['failed'] = True

                # Extraire le PID si disponible
                import re
                pid_match = re.search(r'main pid: (\d+)', status_text)
                if pid_match:
                    status_info['pid'] = int(pid_match.group(1))

            # Ajouter les logs récents si disponible
            try:
                cmd_logs = self._get_systemctl_cmd() + ['--no-pager', '-n', '5', 'status', self.service_name]
                logs_result = subprocess.run(cmd_logs, capture_output=True, text=True)
                if logs_result.returncode == 0:
                    status_info['recent_logs'] = logs_result.stdout.split('\n')[-10:]
            except:
                pass

            return status_info

        except Exception as e:
            return {
                'installed': False,
                'error': str(e)
            }

    def is_installed(self) -> bool:
        """
        Vérifie si le service est installé

        Returns:
            bool: True si le service est installé
        """
        service_file = self.user_service_file if self.use_user_service else self.service_file
        return os.path.exists(service_file)

    def is_running(self) -> bool:
        """
        Vérifie si le service est en cours d'exécution

        Returns:
            bool: True si le service est en cours d'exécution
        """
        try:
            cmd = self._get_systemctl_cmd() + ['is-active', self.service_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout.strip() == 'active'

        except Exception:
            return False

    def _create_service_user(self):
        """
        Crée l'utilisateur système pour le service (services système seulement)
        """
        if self.use_user_service:
            return

        try:
            # Vérifier si l'utilisateur existe déjà
            subprocess.run(['id', 'watchman-agent-client'], capture_output=True, check=True)
            print("✅ Utilisateur 'watchman-agent-client' existe déjà")

        except subprocess.CalledProcessError:
            # Créer l'utilisateur système
            try:
                subprocess.run([
                    'useradd',
                    '--system',
                    '--no-create-home',
                    '--shell', '/usr/sbin/nologin',
                    '--comment', 'Watchman Agent Client Service User',
                    'watchman-agent-client'
                ], check=True, capture_output=True)

                print("✅ Utilisateur système 'watchman-agent-client' créé")

            except subprocess.CalledProcessError as e:
                print(f"⚠️  Impossible de créer l'utilisateur système: {e}")

    def _create_service_directories(self):
        """
        Crée les répertoires nécessaires pour le service
        """
        if self.use_user_service:
            dirs = [
                os.path.expanduser("~/.local/share/watchman-agent-client"),
                os.path.expanduser("~/.config/watchman-agent-client"),
                os.path.expanduser("~/.local/share/watchman-agent-client/logs")
            ]
            owner = None  # Répertoires utilisateur
        else:
            dirs = [
                "/var/lib/watchman-agent-client",
                "/etc/watchman-agent-client",
                "/var/log/watchman-agent-client"
            ]
            owner = "watchman-agent-client"

        for directory in dirs:
            try:
                os.makedirs(directory, mode=0o750, exist_ok=True)

                # Changer le propriétaire pour les services système
                if owner and os.geteuid() == 0:
                    import pwd
                    import grp
                    try:
                        uid = pwd.getpwnam(owner).pw_uid
                        gid = grp.getgrnam(owner).gr_gid
                        os.chown(directory, uid, gid)
                    except KeyError:
                        pass  # Utilisateur n'existe pas encore

                print(f"✅ Répertoire créé: {directory}")

            except Exception as e:
                print(f"⚠️  Erreur création répertoire {directory}: {e}")

    def get_logs(self, lines: int = 50) -> str:
        """
        Récupère les logs du service via journalctl

        Args:
            lines: Nombre de lignes de logs à récupérer

        Returns:
            str: Logs du service
        """
        try:
            cmd = ['journalctl'] + (['--user'] if self.use_user_service else []) + [
                '-u', self.service_name,
                '-n', str(lines),
                '--no-pager'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout

        except Exception as e:
            return f"Erreur récupération logs: {e}"

    def enable_service(self) -> bool:
        """
        Active le service au démarrage

        Returns:
            bool: True si l'activation a réussi
        """
        try:
            cmd = self._get_systemctl_cmd() + ['enable', self.service_name]
            subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Service '{self.service_name}' activé au démarrage")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur activation service: {e}")
            return False

    def disable_service(self) -> bool:
        """
        Désactive le service au démarrage

        Returns:
            bool: True si la désactivation a réussi
        """
        try:
            cmd = self._get_systemctl_cmd() + ['disable', self.service_name]
            subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Service '{self.service_name}' désactivé au démarrage")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur désactivation service: {e}")
            return False