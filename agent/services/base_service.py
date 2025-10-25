"""
Classe de base pour les services système de l'agent d'inventaire

Cette classe définit l'interface commune que tous les services
système doivent implémenter.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseService(ABC):
    """
    Classe de base abstraite pour tous les services système

    Cette classe définit l'interface commune que tous les services
    système (Windows, Linux, macOS) doivent implémenter.
    """

    def __init__(self, service_name: str, display_name: str, description: str):
        """
        Initialise le service de base

        Args:
            service_name: Nom technique du service
            display_name: Nom affiché du service
            description: Description du service
        """
        self.service_name = service_name
        self.display_name = display_name
        self.description = description

        # Agent principal
        self.agent = None

    @abstractmethod
    def install(self) -> bool:
        """
        Installe le service système

        Returns:
            bool: True si l'installation a réussi
        """
        pass

    @abstractmethod
    def uninstall(self) -> bool:
        """
        Désinstalle le service système

        Returns:
            bool: True si la désinstallation a réussi
        """
        pass

    @abstractmethod
    def start_service(self) -> bool:
        """
        Démarre le service système

        Returns:
            bool: True si le démarrage a réussi
        """
        pass

    @abstractmethod
    def stop_service(self) -> bool:
        """
        Arrête le service système

        Returns:
            bool: True si l'arrêt a réussi
        """
        pass

    @abstractmethod
    def restart_service(self) -> bool:
        """
        Redémarre le service système

        Returns:
            bool: True si le redémarrage a réussi
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du service

        Returns:
            dict: Statut détaillé du service
        """
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        """
        Vérifie si le service est installé

        Returns:
            bool: True si le service est installé
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """
        Vérifie si le service est en cours d'exécution

        Returns:
            bool: True si le service est en cours d'exécution
        """
        pass

    def set_agent(self, agent):
        """
        Associe une instance d'agent au service

        Args:
            agent: Instance de WatchmanAgentClient
        """
        self.agent = agent

    def run_agent_service_mode(self):
        """
        Lance l'agent en mode service

        Cette méthode est appelée par le service système
        pour exécuter l'agent.
        """
        if self.agent:
            self.agent.run_service_mode()
        else:
            raise RuntimeError("Aucun agent associé au service")

    def get_service_info(self) -> Dict[str, str]:
        """
        Retourne les informations de base du service

        Returns:
            dict: Informations du service
        """
        return {
            'name': self.service_name,
            'display_name': self.display_name,
            'description': self.description,
            'installed': self.is_installed(),
            'running': self.is_running()
        }