"""
Service Windows pour l'agent d'inventaire

Ce module implémente un service Windows natif utilisant les APIs
Windows Services et pywin32.
"""

import sys
import os
import time
import subprocess
from typing import Dict, Any

# Import conditionnel pour Windows
if sys.platform == "win32":
    try:
        import win32service
        import win32serviceutil
        import win32event
        import win32api
        import winerror
        import servicemanager
    except ImportError:
        print("⚠️  Module pywin32 non disponible. Installation requise: pip install pywin32")
        win32service = None

from .base_service import BaseService


class WindowsInventoryServiceBase(win32serviceutil.ServiceFramework if win32service else object):
    """
    Classe de service Windows pour l'agent d'inventaire

    Cette classe hérite des utilitaires Windows Services et implémente
    les méthodes nécessaires pour fonctionner comme un service Windows.
    """

    # Informations du service
    _svc_name_ = "WatchmanAgent"
    _svc_display_name_ = "Watchman Agent Client"
    _svc_description_ = "Service de surveillance et monitoring système Watchman"

    def __init__(self, args):
        """
        Initialise le service Windows

        Args:
            args: Arguments du service
        """
        if win32service is None:
            raise ImportError("pywin32 requis pour les services Windows")

        super().__init__(args)

        # Événement d'arrêt
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

        # Watchman Agent Client
        self.agent = None

        # Logger pour le service
        self.logger = None

    def SvcStop(self):
        """
        Méthode appelée lors de l'arrêt du service
        """
        # Reporter l'arrêt au SCM
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

        # Log l'arrêt
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPING,
            (self._svc_name_, '')
        )

        # Arrêter l'agent
        if self.agent:
            self.agent.shutdown()

        # Signaler l'arrêt
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        """
        Méthode principale du service - point d'entrée
        """
        # Log le démarrage
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )

        try:
            # Initialiser l'agent d'inventaire
            self._initialize_agent()

            # Démarrer l'agent en mode service
            if self.agent:
                # Log démarrage
                if self.logger:
                    self.logger.info("Démarrage de l'agent en mode service...")

                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    0xF000,
                    ("Agent démarré, initialisation des composants...", '')
                )

                # Démarrer les composants
                self.agent.start_scheduler()
                self.agent.start_web_interface()

                # Vérifier que l'interface web a démarré
                import time
                time.sleep(2)  # Attendre que Flask démarre

                if self.logger:
                    web_config = self.agent.config.get_web_config()
                    self.logger.info(f"Service actif - Interface web sur http://{web_config['host']}:{web_config['port']}")

                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    0xF001,
                    ("Service complètement démarré", '')
                )

                # Attendre l'événement d'arrêt
                win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

            else:
                raise RuntimeError("Impossible d'initialiser l'agent")

        except Exception as e:
            # Log l'erreur
            error_msg = f"Erreur dans le service: {str(e)}"

            servicemanager.LogErrorMsg(error_msg)

            if self.logger:
                self.logger.exception("Exception dans SvcDoRun")

            # Arrêter le service avec erreur
            self.ReportServiceStatus(win32service.SERVICE_STOPPED, win32service.ERROR_SERVICE_SPECIFIC_ERROR)

    def _initialize_agent(self):
        """
        Initialise l'agent d'inventaire pour le service
        """
        try:
            # Importer l'agent (path relatif depuis le service)
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from agent.main import WatchmanAgentClient

            # Créer l'agent avec la config par défaut
            self.agent = WatchmanAgentClient()
            self.logger = self.agent.logger

            if self.logger:
                self.logger.info("Agent initialisé dans le service Windows")

        except Exception as e:
            error_msg = f"Erreur initialisation agent: {str(e)}"
            servicemanager.LogErrorMsg(error_msg)
            raise


# Alias pour compatibilité
WindowsInventoryService = WindowsInventoryServiceBase


class WindowsServiceManager(BaseService):
    """
    Gestionnaire de service Windows pour l'agent d'inventaire

    Cette classe implémente l'interface BaseService pour Windows
    et fournit les méthodes de gestion du service.
    """

    def __init__(self):
        """
        Initialise le gestionnaire de service Windows
        """
        super().__init__(
            service_name="WatchmanAgent",
            display_name="Watchman Agent Client",
            description="Service de surveillance et monitoring système Watchman"
        )

    def install(self) -> bool:
        """
        Installe le service Windows

        Returns:
            bool: True si l'installation a réussi
        """
        if win32service is None:
            print("❌ pywin32 non disponible")
            return False

        try:
            # Chemin vers le script du service
            service_script = os.path.join(
                os.path.dirname(__file__),
                "windows_service.py"
            )

            # Installer le service
            win32serviceutil.InstallService(
                pythonClassString=f"{__name__}.WindowsInventoryService",
                serviceName=self.service_name,
                displayName=self.display_name,
                description=self.description,
                startType=win32service.SERVICE_AUTO_START,
                exeName=sys.executable
            )

            print(f"✅ Service '{self.display_name}' installé avec succès")
            return True

        except Exception as e:
            print(f"❌ Erreur installation service: {e}")
            return False

    def uninstall(self) -> bool:
        """
        Désinstalle le service Windows

        Returns:
            bool: True si la désinstallation a réussi
        """
        if win32service is None:
            return False

        try:
            # Arrêter le service s'il tourne
            if self.is_running():
                self.stop_service()

            # Désinstaller le service
            win32serviceutil.RemoveService(self.service_name)

            print(f"Service '{self.display_name}' désinstallé avec succès")
            return True

        except Exception as e:
            print(f"Erreur désinstallation service: {e}")
            return False

    def start_service(self) -> bool:
        """
        Démarre le service Windows

        Returns:
            bool: True si le démarrage a réussi
        """
        if win32service is None:
            return False

        try:
            win32serviceutil.StartService(self.service_name)
            print(f"Service '{self.display_name}' démarré")
            return True

        except Exception as e:
            print(f"Erreur démarrage service: {e}")
            return False

    def stop_service(self) -> bool:
        """
        Arrête le service Windows

        Returns:
            bool: True si l'arrêt a réussi
        """
        if win32service is None:
            return False

        try:
            win32serviceutil.StopService(self.service_name)
            print(f"Service '{self.display_name}' arrêté")
            return True

        except Exception as e:
            print(f"Erreur arrêt service: {e}")
            return False

    def restart_service(self) -> bool:
        """
        Redémarre le service Windows

        Returns:
            bool: True si le redémarrage a réussi
        """
        if win32service is None:
            return False

        try:
            win32serviceutil.RestartService(self.service_name)
            print(f"✅ Service '{self.display_name}' redémarré")
            return True

        except Exception as e:
            print(f"❌ Erreur redémarrage service: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du service Windows

        Returns:
            dict: Statut détaillé du service
        """
        if win32service is None:
            return {
                'status': 'unknown',
                'error': 'pywin32 non disponible'
            }

        try:
            # Ouvrir le gestionnaire de services
            hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)

            try:
                # Ouvrir le service
                hs = win32service.OpenService(hscm, self.service_name, win32service.SERVICE_QUERY_STATUS)

                try:
                    # Récupérer le statut
                    status = win32service.QueryServiceStatus(hs)

                    # Mapper les codes de statut
                    status_map = {
                        win32service.SERVICE_STOPPED: 'stopped',
                        win32service.SERVICE_START_PENDING: 'starting',
                        win32service.SERVICE_STOP_PENDING: 'stopping',
                        win32service.SERVICE_RUNNING: 'running',
                        win32service.SERVICE_CONTINUE_PENDING: 'resuming',
                        win32service.SERVICE_PAUSE_PENDING: 'pausing',
                        win32service.SERVICE_PAUSED: 'paused'
                    }

                    return {
                        'status': status_map.get(status[1], 'unknown'),
                        'service_type': status[0],
                        'current_state': status[1],
                        'controls_accepted': status[2],
                        'win32_exit_code': status[3],
                        'service_specific_exit_code': status[4],
                        'check_point': status[5],
                        'wait_hint': status[6]
                    }

                finally:
                    win32service.CloseServiceHandle(hs)

            finally:
                win32service.CloseServiceHandle(hscm)

        except win32api.error as e:
            if e.winerror == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
                return {'status': 'not_installed'}
            else:
                return {
                    'status': 'error',
                    'error': str(e)
                }

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def is_installed(self) -> bool:
        """
        Vérifie si le service est installé

        Returns:
            bool: True si le service est installé
        """
        status = self.get_status()
        return status.get('status') != 'not_installed'

    def is_running(self) -> bool:
        """
        Vérifie si le service est en cours d'exécution

        Returns:
            bool: True si le service est en cours d'exécution
        """
        status = self.get_status()
        return status.get('status') == 'running'


def handle_service_command():
    """
    Gestionnaire de commandes pour le service Windows

    Cette fonction gère les commandes install, remove, start, stop
    quand le script est exécuté directement.
    """
    if len(sys.argv) == 1:
        # Si aucun argument, essayer de démarrer le service
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(WindowsInventoryService)
            servicemanager.StartServiceCtrlDispatcher()
        except Exception as e:
            print(f"Erreur démarrage service: {e}")

    else:
        # Gérer les arguments de ligne de commande
        if sys.argv[1] == 'install':
            service_manager = WindowsServiceManager()
            service_manager.install()

        elif sys.argv[1] == 'remove' or sys.argv[1] == 'uninstall':
            service_manager = WindowsServiceManager()
            service_manager.uninstall()

        elif sys.argv[1] == 'start':
            service_manager = WindowsServiceManager()
            service_manager.start_service()

        elif sys.argv[1] == 'stop':
            service_manager = WindowsServiceManager()
            service_manager.stop_service()

        elif sys.argv[1] == 'restart':
            service_manager = WindowsServiceManager()
            service_manager.restart_service()

        elif sys.argv[1] == 'status':
            service_manager = WindowsServiceManager()
            status = service_manager.get_status()
            print(f"Statut du service: {status}")

        else:
            # Laisser win32serviceutil gérer les autres commandes
            if win32service is not None:
                win32serviceutil.HandleCommandLine(WindowsInventoryService)


if __name__ == '__main__':
    handle_service_command()