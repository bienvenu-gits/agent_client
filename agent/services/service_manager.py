"""
Module de gestion des services système natifs pour les trois OS principaux.
Supporte Windows Service, systemd (Linux), et launchd (macOS).
"""
import os
import sys
import platform
import subprocess
import ctypes
from pathlib import Path
from typing import Optional, Dict, Any

from agent.core.logger import AgentLogger


class ServiceManager:
    """Gestionnaire de services système multi-plateforme"""

    def __init__(self, service_name: str = "watchman-agent-client"):
        self.service_name = service_name
        self.logger = AgentLogger().get_logger()
        self.system = platform.system()
        self.executable_path = self._get_executable_path()
        print(f"ServiceManager initialized for {self.system} with executable at {self.executable_path}")

    def _get_executable_path(self) -> str:
        """Retourne le chemin de l'exécutable watchman-agent"""
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            venv_path = os.environ.get('VIRTUAL_ENV')
            if venv_path:
                if self.system == "Windows":
                    executable = os.path.join(venv_path, 'Scripts', 'watchman-agent-client.exe')
                else:
                    executable = os.path.join(venv_path, 'bin', 'watchman-agent-client')
                if os.path.exists(executable):
                    return executable
            
            import shutil
            found = shutil.which('watchman-agent-client')
            if found:
                return found
            
            python_exec = sys.executable
            return f"{python_exec} -m agent.main"

    @staticmethod
    def is_admin() -> bool:
        """Vérifie si le script s'exécute avec les privilèges administrateur"""
        if platform.system() != "Windows":
            return os.geteuid() == 0
        
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def request_admin_privileges_and_relaunch(self) -> bool:
        """
        Relance le programme avec élévation UAC sur Windows.
        
        IMPORTANT: Cette fonction quitte le programme actuel si l'élévation réussit.
        Elle ne retourne True que si on est déjà admin.
        
        Returns:
            bool: True si déjà admin, False si élévation impossible, sinon quitte
        """
        if self.system != "Windows":
            self.logger.warning("L'élévation des privilèges n'est disponible que sur Windows")
            return False
        
        if self.is_admin():
            return True  # Déjà admin
        
        self.logger.warning("⚠️ Privilèges administrateur requis pour gérer les services Windows")
        self.logger.info("Demande d'élévation des privilèges...")
        
        try:
            # Construire les arguments pour relancer
            # Garder exactement les mêmes arguments
            params = " ".join(sys.argv[1:])  # Tous les args sauf le nom du programme
            
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                params,
                None,
                1
            )
            
            if ret > 32:  # Succès
                self.logger.info("✓ Programme relancé avec privilèges administrateur")
                sys.exit(0)  # Quitter l'instance non-admin
            else:
                self.logger.error("✗ Élévation refusée par l'utilisateur")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la demande d'élévation: {e}")
            return False

    def install_service(self) -> bool:
        """
        Installe le service selon l'OS
        
        Returns:
            bool: True si installation réussie
        """
        try:
            # Pour Windows, vérifier/demander les privilèges admin
            if self.system == "Windows":
                if not self.is_admin():
                    self.logger.error("❌ Privilèges administrateur requis pour installer un service Windows")
                    self.logger.info("💡 Conseil: Lancez cette commande depuis un terminal administrateur")
                    self.logger.info("   OU le programme demandera automatiquement l'élévation UAC")
                    
                    # Tenter l'élévation automatique
                    # Si ça réussit, cette fonction ne retournera jamais (sys.exit)
                    # Si ça échoue, on continue et retourne False
                    self.request_admin_privileges_and_relaunch()
                    return False
                
                return self._install_windows_service()
            
            elif self.system == "Linux":
                return self._install_systemd_service()
            elif self.system == "Darwin":
                return self._install_launchd_service()
            else:
                self.logger.error(f"OS non supporté: {self.system}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'installation du service: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def uninstall_service(self) -> bool:
        """Désinstalle le service selon l'OS"""
        try:
            if self.system == "Windows":
                if not self.is_admin():
                    self.logger.error("❌ Privilèges administrateur requis pour désinstaller un service Windows")
                    self.request_admin_privileges_and_relaunch()
                    return False
                return self._uninstall_windows_service()
            
            elif self.system == "Linux":
                return self._uninstall_systemd_service()
            elif self.system == "Darwin":
                return self._uninstall_launchd_service()
            else:
                self.logger.error(f"OS non supporté: {self.system}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la désinstallation du service: {e}")
            return False

    def start_service(self) -> bool:
        """Démarre le service"""
        try:
            if self.system == "Windows":
                if not self.is_admin():
                    self.logger.error("❌ Privilèges administrateur requis")
                    self.request_admin_privileges_and_relaunch()
                    return False
                    
                result = subprocess.run(['sc', 'start', self.service_name],
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.logger.info(f"✅ Service '{self.service_name}' démarré avec succès")
                    return True
                else:
                    self.logger.error(f"❌ Échec du démarrage: {result.stderr}")
                    return False
                    
            elif self.system == "Linux":
                result = subprocess.run(['sudo', 'systemctl', 'start', f'{self.service_name}.service'],
                                      capture_output=True, text=True)
                return result.returncode == 0
            elif self.system == "Darwin":
                result = subprocess.run(['sudo', 'launchctl', 'load', f'/Library/LaunchDaemons/{self.service_name}.plist'],
                                      capture_output=True, text=True)
                return result.returncode == 0
                
        except Exception as e:
            self.logger.error(f"Erreur lors du démarrage du service: {e}")
            return False

    def stop_service(self) -> bool:
        """Arrête le service"""
        try:
            if self.system == "Windows":
                if not self.is_admin():
                    self.logger.error("❌ Privilèges administrateur requis")
                    self.request_admin_privileges_and_relaunch()
                    return False
                    
                result = subprocess.run(['sc', 'stop', self.service_name],
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.logger.info(f"✅ Service '{self.service_name}' arrêté avec succès")
                    return True
                else:
                    self.logger.error(f"❌ Échec de l'arrêt: {result.stderr}")
                    return False
                    
            elif self.system == "Linux":
                result = subprocess.run(['sudo', 'systemctl', 'stop', f'{self.service_name}.service'],
                                      capture_output=True, text=True)
                return result.returncode == 0
            elif self.system == "Darwin":
                result = subprocess.run(['sudo', 'launchctl', 'unload', f'/Library/LaunchDaemons/{self.service_name}.plist'],
                                      capture_output=True, text=True)
                return result.returncode == 0
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'arrêt du service: {e}")
            return False

    def get_service_status(self) -> Dict[str, Any]:
        """Retourne l'état du service"""
        try:
            if self.system == "Windows":
                result = subprocess.run(['sc', 'query', self.service_name],
                                      capture_output=True, text=True)
                return {
                    'installed': result.returncode == 0,
                    'running': 'RUNNING' in result.stdout if result.returncode == 0 else False,
                    'output': result.stdout
                }
            elif self.system == "Linux":
                result = subprocess.run(['systemctl', 'is-active', f'{self.service_name}.service'],
                                      capture_output=True, text=True)
                is_installed = subprocess.run(['systemctl', 'list-unit-files', f'{self.service_name}.service'],
                                            capture_output=True, text=True).returncode == 0
                return {
                    'installed': is_installed,
                    'running': result.stdout.strip() == 'active',
                    'output': result.stdout
                }
            elif self.system == "Darwin":
                result = subprocess.run(['launchctl', 'list', self.service_name],
                                      capture_output=True, text=True)
                return {
                    'installed': os.path.exists(f'/Library/LaunchDaemons/{self.service_name}.plist'),
                    'running': result.returncode == 0,
                    'output': result.stdout
                }
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du service: {e}")
            return {'installed': False, 'running': False, 'output': str(e)}

    # ========== WINDOWS SERVICE ==========
    def _install_windows_service(self) -> bool:
        """Installe un service Windows avec sc.exe"""
        
        # On est déjà admin ici (vérifié dans install_service)
        self.logger.info(f"🔧 Installation du service Windows '{self.service_name}'...")
        self.logger.info(f"📍 Exécutable: {self.executable_path}")
        
        command = f'"{self.executable_path}"'

        # Création du service
        cmd = [
            'sc', 'create', self.service_name,
            f'binPath={command}',
            f'DisplayName=Watchman Agent Client',
            'obj=LocalSystem',  # Compte système
            'start=auto'
        ]

        self.logger.info(f"🚀 Commande: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            self.logger.error(f"❌ Échec création service Windows:")
            self.logger.error(f"   stdout: {result.stdout}")
            self.logger.error(f"   stderr: {result.stderr}")
            return False

        # Configuration description
        subprocess.run([
            'sc', 'description', self.service_name,
            'Service pour collecter des informations système et les envoyer à une API centrale.'
        ], capture_output=True)

        # Configuration pour redémarrage automatique
        subprocess.run([
            'sc', 'failure', self.service_name,
            'reset=86400',
            'actions=restart/5000/restart/10000/restart/20000'
        ], capture_output=True)

        self.logger.info(f"✅ Service Windows '{self.service_name}' installé avec succès")
        self.logger.info(f"💡 Pour démarrer le service: sc start {self.service_name}")
        return True

    def _uninstall_windows_service(self) -> bool:
        """Désinstalle le service Windows"""
        self.logger.info(f"🗑️ Désinstallation du service '{self.service_name}'...")
        
        # Arrêt du service
        subprocess.run(['sc', 'stop', self.service_name], capture_output=True)
        
        import time
        time.sleep(2)  # Attendre que le service s'arrête

        # Suppression du service
        result = subprocess.run(['sc', 'delete', self.service_name], 
                              capture_output=True, text=True)

        if result.returncode != 0:
            self.logger.error(f"❌ Échec suppression service Windows:")
            self.logger.error(f"   {result.stderr}")
            return False

        self.logger.info(f"✅ Service Windows '{self.service_name}' désinstallé avec succès")
        return True

    # ========== SYSTEMD (LINUX) ==========
    def _install_systemd_service(self) -> bool:
        """Installe un service systemd"""
        service_content = f"""[Unit]
Description=Watchman Agent Client Service
After=network.target
Wants=network.target

[Service]
Type=exec
User=root
Group=root
ExecStart={self.executable_path}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier={self.service_name}

[Install]
WantedBy=multi-user.target
"""

        service_file = f'/etc/systemd/system/{self.service_name}.service'

        try:
            # Écriture du fichier de service
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.service') as tmp:
                tmp.write(service_content)
                tmp_path = tmp.name

            # Copie vers le répertoire systemd (nécessite sudo)
            result = subprocess.run(['sudo', 'cp', tmp_path, service_file],
                                  capture_output=True, text=True)
            os.unlink(tmp_path)

            if result.returncode != 0:
                self.logger.error(f"Échec copie fichier service: {result.stderr}")
                return False

            # Rechargement systemd
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
            subprocess.run(['sudo', 'systemctl', 'enable', f'{self.service_name}.service'])

            self.logger.info(f"Service systemd '{self.service_name}' installé avec succès")
            return True

        except Exception as e:
            self.logger.error(f"Erreur installation systemd: {e}")
            return False

    def _uninstall_systemd_service(self) -> bool:
        """Désinstalle le service systemd"""
        try:
            # Arrêt et désactivation
            subprocess.run(['sudo', 'systemctl', 'stop', f'{self.service_name}.service'])
            subprocess.run(['sudo', 'systemctl', 'disable', f'{self.service_name}.service'])

            # Suppression du fichier
            service_file = f'/etc/systemd/system/{self.service_name}.service'
            result = subprocess.run(['sudo', 'rm', '-f', service_file],
                                  capture_output=True, text=True)

            # Rechargement systemd
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'])

            if result.returncode != 0:
                self.logger.error(f"Échec suppression service systemd: {result.stderr}")
                return False

            self.logger.info(f"Service systemd '{self.service_name}' désinstallé avec succès")
            return True

        except Exception as e:
            self.logger.error(f"Erreur désinstallation systemd: {e}")
            return False

    # ========== LAUNCHD (MACOS) ==========
    def _install_launchd_service(self) -> bool:
        """Installe un service launchd sur macOS"""
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.service_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{self.executable_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/var/log/{self.service_name}.log</string>
    <key>StandardOutPath</key>
    <string>/var/log/{self.service_name}.log</string>
</dict>
</plist>
"""

        plist_file = f'/Library/LaunchDaemons/{self.service_name}.plist'

        try:
            # Écriture du fichier plist
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.plist') as tmp:
                tmp.write(plist_content)
                tmp_path = tmp.name

            # Copie vers le répertoire LaunchDaemons
            result = subprocess.run(['sudo', 'cp', tmp_path, plist_file],
                                  capture_output=True, text=True)
            os.unlink(tmp_path)

            if result.returncode != 0:
                self.logger.error(f"Échec copie fichier plist: {result.stderr}")
                return False

            # Configuration des permissions
            subprocess.run(['sudo', 'chown', 'root:wheel', plist_file])
            subprocess.run(['sudo', 'chmod', '644', plist_file])

            # Chargement du service
            subprocess.run(['sudo', 'launchctl', 'load', plist_file])

            self.logger.info(f"Service launchd '{self.service_name}' installé avec succès")
            return True

        except Exception as e:
            self.logger.error(f"Erreur installation launchd: {e}")
            return False

    def _uninstall_launchd_service(self) -> bool:
        """Désinstalle le service launchd"""
        try:
            plist_file = f'/Library/LaunchDaemons/{self.service_name}.plist'

            # Déchargement du service
            subprocess.run(['sudo', 'launchctl', 'unload', plist_file])

            # Suppression du fichier
            result = subprocess.run(['sudo', 'rm', '-f', plist_file],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.error(f"Échec suppression service launchd: {result.stderr}")
                return False

            self.logger.info(f"Service launchd '{self.service_name}' désinstallé avec succès")
            return True

        except Exception as e:
            self.logger.error(f"Erreur désinstallation launchd: {e}")
            return False