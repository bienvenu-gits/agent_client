"""
Service macOS (launchd) pour l'agent d'inventaire

Ce module implémente un service launchd natif macOS
pour l'agent d'inventaire.
"""

import os
import sys
import subprocess
import plistlib
from typing import Dict, Any
from pathlib import Path

from .base_service import BaseService


class MacOSLaunchdService(BaseService):
    """
    Gestionnaire de service launchd pour l'agent d'inventaire

    Cette classe implémente l'interface BaseService pour macOS
    et gère les services launchd.
    """

    def __init__(self):
        """
        Initialise le gestionnaire de service launchd
        """
        super().__init__(
            service_name="com.watchman.agent.client",
            display_name="Watchman Agent Client",
            description="Watchman system monitoring and surveillance service"
        )

        # Chemins launchd
        self.system_plist_path = f"/Library/LaunchDaemons/{self.service_name}.plist"
        self.user_plist_path = f"{os.path.expanduser('~')}/Library/LaunchAgents/{self.service_name}.plist"

        # Déterminer si on utilise les services système ou utilisateur
        self.use_user_service = os.geteuid() != 0  # Non-root utilise user agent

        # Chemin du plist actuel
        self.plist_path = self.user_plist_path if self.use_user_service else self.system_plist_path

    def _get_launchctl_cmd(self, service_name: str = None) -> list:
        """
        Retourne la commande launchctl appropriée

        Args:
            service_name: Nom du service (optionnel)

        Returns:
            list: Commande launchctl avec les bons paramètres
        """
        cmd = ['launchctl']

        # Ajouter le nom du service si fourni
        if service_name:
            cmd.append(service_name)

        return cmd

    def _get_plist_content(self) -> Dict[str, Any]:
        """
        Génère le contenu du fichier plist pour launchd

        Returns:
            dict: Contenu du fichier .plist
        """
        # Déterminer le chemin vers l'exécutable Python et le script
        python_executable = sys.executable
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")

        # Répertoires de travail et configuration
        if self.use_user_service:
            working_dir = os.path.expanduser("~/Library/Application Support/WatchmanAgentClient")
            config_file = os.path.expanduser("~/Library/Preferences/WatchmanAgentClient/config.ini")
            log_path = os.path.expanduser("~/Library/Logs/WatchmanAgentClient")
        else:
            working_dir = "/var/lib/watchman-agent-client"
            config_file = "/etc/watchman-agent-client/config.ini"
            log_path = "/var/log/watchman-agent-client"

        # Créer les répertoires nécessaires
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        os.makedirs(log_path, exist_ok=True)

        plist_data = {
            'Label': self.service_name,
            'ProgramArguments': [
                python_executable,
                script_path,
                '--mode', 'service',
                '--config', config_file
            ],
            'WorkingDirectory': working_dir,
            'RunAtLoad': True,
            'KeepAlive': {
                'SuccessfulExit': False,  # Redémarrer si l'agent s'arrête anormalement
                'Crashed': True  # Redémarrer si l'agent plante
            },
            'StandardOutPath': os.path.join(log_path, 'agent.stdout.log'),
            'StandardErrorPath': os.path.join(log_path, 'agent.stderr.log'),
            'ProcessType': 'Background',
            'Nice': 10,  # Priorité plus basse
        }

        # Configuration spécifique selon le type de service
        if self.use_user_service:
            # Service utilisateur (LaunchAgent)
            plist_data.update({
                'LimitLoadToSessionType': ['Aqua'],  # Seulement pour sessions graphiques
                'ThrottleInterval': 60,  # Limite le redémarrage rapide
            })
        else:
            # Service système (LaunchDaemon)
            plist_data.update({
                'UserName': '_watchman-agent-client',  # Utilisateur système dédié
                'GroupName': '_watchman-agent-client',
                'InitGroups': True,
                'StartInterval': 3600,  # Démarrer toutes les heures si pas déjà en cours
                'ThrottleInterval': 60,
            })

        # Programmation périodique (optionnel - peut être géré par l'agent lui-même)
        # plist_data['StartCalendarInterval'] = {
        #     'Hour': 2,  # 2h du matin
        #     'Minute': 0
        # }

        return plist_data

    def install(self) -> bool:
        """
        Installe le service launchd

        Returns:
            bool: True si l'installation a réussi
        """
        try:
            # Créer l'utilisateur système si nécessaire (services système seulement)
            if not self.use_user_service:
                self._create_service_user()

            # Créer les répertoires nécessaires
            self._create_service_directories()

            # Créer le répertoire du plist
            os.makedirs(os.path.dirname(self.plist_path), exist_ok=True)

            # Générer et écrire le fichier plist
            plist_content = self._get_plist_content()

            with open(self.plist_path, 'wb') as f:
                plistlib.dump(plist_content, f)

            print(f"✅ Fichier plist créé: {self.plist_path}")

            # Définir les permissions appropriées
            if not self.use_user_service:
                os.chmod(self.plist_path, 0o644)

            # Charger le service
            self._load_service()

            print(f"✅ Service '{self.service_name}' installé")
            return True

        except Exception as e:
            print(f"❌ Erreur installation service: {e}")
            return False

    def uninstall(self) -> bool:
        """
        Désinstalle le service launchd

        Returns:
            bool: True si la désinstallation a réussi
        """
        try:
            # Arrêter et décharger le service
            if self.is_running():
                self.stop_service()

            self._unload_service()

            # Supprimer le fichier plist
            if os.path.exists(self.plist_path):
                os.remove(self.plist_path)
                print(f"✅ Fichier plist supprimé: {self.plist_path}")

            print(f"✅ Service '{self.service_name}' désinstallé")
            return True

        except Exception as e:
            print(f"❌ Erreur désinstallation service: {e}")
            return False

    def start_service(self) -> bool:
        """
        Démarre le service launchd

        Returns:
            bool: True si le démarrage a réussi
        """
        try:
            # Charger le service s'il n'est pas déjà chargé
            self._load_service()

            # Démarrer le service
            cmd = ['launchctl', 'start', self.service_name]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✅ Service '{self.service_name}' démarré")
                return True
            else:
                print(f"❌ Erreur démarrage service: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Erreur démarrage service: {e}")
            return False

    def stop_service(self) -> bool:
        """
        Arrête le service launchd

        Returns:
            bool: True si l'arrêt a réussi
        """
        try:
            cmd = ['launchctl', 'stop', self.service_name]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✅ Service '{self.service_name}' arrêté")
                return True
            else:
                print(f"❌ Erreur arrêt service: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Erreur arrêt service: {e}")
            return False

    def restart_service(self) -> bool:
        """
        Redémarre le service launchd

        Returns:
            bool: True si le redémarrage a réussi
        """
        try:
            # Arrêter puis redémarrer
            self.stop_service()
            time.sleep(2)  # Attendre un peu
            return self.start_service()

        except Exception as e:
            print(f"❌ Erreur redémarrage service: {e}")
            return False

    def _load_service(self) -> bool:
        """
        Charge le service dans launchd

        Returns:
            bool: True si le chargement a réussi
        """
        try:
            cmd = ['launchctl', 'load', self.plist_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return True
            else:
                # Le service peut déjà être chargé
                if "already loaded" in result.stderr.lower():
                    return True
                else:
                    print(f"⚠️  Avertissement chargement service: {result.stderr}")
                    return True

        except Exception as e:
            print(f"❌ Erreur chargement service: {e}")
            return False

    def _unload_service(self) -> bool:
        """
        Décharge le service de launchd

        Returns:
            bool: True si le déchargement a réussi
        """
        try:
            cmd = ['launchctl', 'unload', self.plist_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return True
            else:
                # Le service peut ne pas être chargé
                if "not loaded" in result.stderr.lower() or "could not find" in result.stderr.lower():
                    return True
                else:
                    print(f"⚠️  Avertissement déchargement service: {result.stderr}")
                    return True

        except Exception as e:
            print(f"❌ Erreur déchargement service: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du service launchd

        Returns:
            dict: Statut détaillé du service
        """
        try:
            # Utiliser launchctl list pour récupérer le statut
            cmd = ['launchctl', 'list', self.service_name]
            result = subprocess.run(cmd, capture_output=True, text=True)

            status_info = {
                'installed': self.is_installed(),
                'loaded': False,
                'running': False,
                'pid': None,
                'exit_status': None
            }

            if result.returncode == 0:
                # Parser la sortie de launchctl list
                output_lines = result.stdout.strip().split('\n')

                for line in output_lines:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        pid_str = parts[0]
                        exit_status_str = parts[1]
                        label = parts[2]

                        if label == self.service_name:
                            status_info['loaded'] = True

                            # Vérifier si le service tourne (PID disponible)
                            if pid_str != '-':
                                try:
                                    status_info['pid'] = int(pid_str)
                                    status_info['running'] = True
                                except ValueError:
                                    pass

                            # Statut de sortie
                            if exit_status_str != '-':
                                try:
                                    status_info['exit_status'] = int(exit_status_str)
                                except ValueError:
                                    pass

            else:
                # Le service n'est probablement pas chargé
                if "could not find" in result.stderr.lower():
                    status_info['loaded'] = False

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
        return os.path.exists(self.plist_path)

    def is_running(self) -> bool:
        """
        Vérifie si le service est en cours d'exécution

        Returns:
            bool: True si le service est en cours d'exécution
        """
        status = self.get_status()
        return status.get('running', False)

    def _create_service_user(self):
        """
        Crée l'utilisateur système pour le service (services système seulement)
        """
        if self.use_user_service:
            return

        try:
            # Sur macOS, utiliser dscl pour créer l'utilisateur
            username = "_watchman-agent-client"

            # Vérifier si l'utilisateur existe déjà
            cmd = ['dscl', '.', 'read', f'/Users/{username}']
            result = subprocess.run(cmd, capture_output=True)

            if result.returncode == 0:
                print(f"✅ Utilisateur '{username}' existe déjà")
                return

            # Créer l'utilisateur système
            # Trouver un UID libre (généralement > 200 pour les utilisateurs système sur macOS)
            for uid in range(200, 400):
                cmd_check = ['dscl', '.', 'list', '/Users', 'UniqueID']
                result_check = subprocess.run(cmd_check, capture_output=True, text=True)

                if str(uid) not in result_check.stdout:
                    break
            else:
                uid = 299  # Fallback

            # Créer l'utilisateur
            commands = [
                ['dscl', '.', 'create', f'/Users/{username}'],
                ['dscl', '.', 'create', f'/Users/{username}', 'UserShell', '/usr/bin/false'],
                ['dscl', '.', 'create', f'/Users/{username}', 'RealName', 'Watchman Agent Client Service'],
                ['dscl', '.', 'create', f'/Users/{username}', 'UniqueID', str(uid)],
                ['dscl', '.', 'create', f'/Users/{username}', 'PrimaryGroupID', '1'],  # wheel group
                ['dscl', '.', 'create', f'/Users/{username}', 'NFSHomeDirectory', '/var/empty'],
            ]

            for cmd in commands:
                subprocess.run(cmd, check=True, capture_output=True)

            print(f"✅ Utilisateur système '{username}' créé (UID: {uid})")

        except subprocess.CalledProcessError as e:
            print(f"⚠️  Erreur création utilisateur système: {e}")
        except Exception as e:
            print(f"⚠️  Erreur inattendue création utilisateur: {e}")

    def _create_service_directories(self):
        """
        Crée les répertoires nécessaires pour le service
        """
        if self.use_user_service:
            dirs = [
                os.path.expanduser("~/Library/Application Support/WatchmanAgentClient"),
                os.path.expanduser("~/Library/Preferences/WatchmanAgentClient"),
                os.path.expanduser("~/Library/Logs/WatchmanAgentClient")
            ]
            owner = None
        else:
            dirs = [
                "/var/lib/watchman-agent-client",
                "/etc/watchman-agent-client",
                "/var/log/watchman-agent-client"
            ]
            owner = "_watchman-agent-client"

        for directory in dirs:
            try:
                os.makedirs(directory, mode=0o755, exist_ok=True)

                # Changer le propriétaire pour les services système
                if owner and os.geteuid() == 0:
                    try:
                        import pwd
                        uid = pwd.getpwnam(owner).pw_uid
                        os.chown(directory, uid, 1)  # Group wheel
                    except KeyError:
                        pass  # Utilisateur n'existe pas encore

                print(f"✅ Répertoire créé: {directory}")

            except Exception as e:
                print(f"⚠️  Erreur création répertoire {directory}: {e}")

    def get_logs(self, lines: int = 50) -> str:
        """
        Récupère les logs du service

        Args:
            lines: Nombre de lignes de logs à récupérer

        Returns:
            str: Logs du service
        """
        try:
            if self.use_user_service:
                log_dir = os.path.expanduser("~/Library/Logs/WatchmanAgentClient")
            else:
                log_dir = "/var/log/watchman-agent-client"

            # Lire les fichiers de log
            logs = ""

            # Log stdout
            stdout_log = os.path.join(log_dir, "agent.stdout.log")
            if os.path.exists(stdout_log):
                try:
                    with open(stdout_log, 'r') as f:
                        stdout_lines = f.readlines()
                        logs += "=== STDOUT ===\n"
                        logs += "".join(stdout_lines[-lines:])
                        logs += "\n"
                except Exception:
                    pass

            # Log stderr
            stderr_log = os.path.join(log_dir, "agent.stderr.log")
            if os.path.exists(stderr_log):
                try:
                    with open(stderr_log, 'r') as f:
                        stderr_lines = f.readlines()
                        logs += "=== STDERR ===\n"
                        logs += "".join(stderr_lines[-lines:])
                except Exception:
                    pass

            return logs if logs else "Aucun log disponible"

        except Exception as e:
            return f"Erreur récupération logs: {e}"

    def enable_service(self) -> bool:
        """
        Active le service au démarrage (équivalent de load)

        Returns:
            bool: True si l'activation a réussi
        """
        return self._load_service()

    def disable_service(self) -> bool:
        """
        Désactive le service au démarrage (équivalent de unload)

        Returns:
            bool: True si la désactivation a réussi
        """
        return self._unload_service()