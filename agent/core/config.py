"""
Module de configuration pour l'agent d'inventaire

Ce module gère la configuration de l'agent, incluant :
- Lecture des fichiers de configuration
- Validation des paramètres
- Valeurs par défaut
- Configuration spécifique par plateforme
"""

import os
import sys
import configparser
from pathlib import Path
from typing import Dict, Any, Optional


class AgentConfig:
    """
    Gestionnaire de configuration pour l'agent d'inventaire

    Cette classe centralise la gestion de toute la configuration de l'agent,
    incluant les paramètres serveur, agent, et interface web.
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialise la configuration de l'agent

        Args:
            config_file: Chemin vers le fichier de configuration (optionnel)
        """
        self.config = configparser.ConfigParser()
        self.config_file = config_file or self._get_default_config_path()

        # Définir les valeurs par défaut
        self._set_defaults()

        # Charger la configuration depuis le fichier
        self._load_config()

    def _get_default_config_path(self) -> str:
        """
        Détermine le chemin par défaut du fichier de configuration selon la plateforme

        Returns:
            str: Chemin vers le fichier de configuration
        """
        if sys.platform == "win32":
            # Windows: utilise le dossier Program Files (même que l'installateur)
            return os.path.join(
                os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                "Watchman Agent Client",
                "config",
                "default.conf"
            )
        elif sys.platform == "darwin":
            # macOS: utilise /etc
            return "/etc/watchman-agent-client/config.ini"
        else:
            # Linux et autres Unix: utilise /etc
            return "/etc/watchman-agent-client/config.ini"

    def _set_defaults(self):
        """
        Définit les valeurs de configuration par défaut

        Ces valeurs sont utilisées si aucun fichier de configuration n'est trouvé
        ou si certaines sections/clés sont manquantes.
        """
        # Configuration serveur
        self.config.add_section('server')
        self.config.set('server', 'url', 'http://localhost:8000/api/v1/inventory')
        self.config.set('server', 'auth_token', '')
        self.config.set('server', 'timeout', '30')
        self.config.set('server', 'verify_ssl', 'false')

        # Configuration agent
        self.config.add_section('agent')
        self.config.set('agent', 'reporting_frequency', 'daily')  # daily, weekly, monthly
        self.config.set('agent', 'log_level', 'INFO')
        self.config.set('agent', 'collect_software', 'true')
        self.config.set('agent', 'collect_hardware', 'true')
        self.config.set('agent', 'collect_network', 'true')

        # Configuration interface web
        self.config.add_section('web_interface')
        self.config.set('web_interface', 'enabled', 'true')
        self.config.set('web_interface', 'port', '18743')
        self.config.set('web_interface', 'host', '127.0.0.1')

        # Configuration logging
        self.config.add_section('logging')
        self.config.set('logging', 'log_file', self._get_default_log_path())
        self.config.set('logging', 'max_log_size', '10485760')  # 10MB
        self.config.set('logging', 'backup_count', '5')

    def _get_default_log_path(self) -> str:
        """
        Détermine le chemin par défaut des logs selon la plateforme

        Returns:
            str: Chemin vers le fichier de log
        """
        if sys.platform == "win32":
            return os.path.join(
                os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
                "WatchmanAgentClient",
                "logs",
                "agent.log"
            )
        else:
            return "/var/log/watchman-agent-client/agent.log"

    def _load_config(self):
        """
        Charge la configuration depuis le fichier

        Si le fichier n'existe pas, utilise les valeurs par défaut.
        En cas d'erreur de lecture, log l'erreur et continue avec les défauts.
        """
        try:
            # Charger le fichier de configuration principal
            if os.path.exists(self.config_file):
                self.config.read(self.config_file)
                print(f"Configuration chargée depuis: {self.config_file}")
            else:
                print(f"Fichier de configuration non trouvé: {self.config_file}")
                print("Utilisation des valeurs par défaut")

            # Charger aussi le fichier server.conf créé par l'installateur (prioritaire)
            self._load_installer_config()

        except Exception as e:
            print(f"Erreur lors du chargement de la configuration: {e}")
            print("Utilisation des valeurs par défaut")

    def _load_installer_config(self):
        """
        Charge la configuration serveur créée par l'installateur Inno Setup

        Cette configuration a priorité sur la configuration par défaut.
        """
        try:
            # Chemin vers le fichier server.conf créé par l'installateur
            if sys.platform == "win32":
                installer_config_path = os.path.join(
                    os.path.dirname(self.config_file),  # Même dossier que config.ini
                    "server.conf"
                )
            else:
                installer_config_path = "/etc/watchman-agent-client/server.conf"

            if os.path.exists(installer_config_path):
                installer_config = configparser.ConfigParser()
                installer_config.read(installer_config_path)

                # Copier les sections du fichier installateur vers la config principale
                for section_name in installer_config.sections():
                    if not self.config.has_section(section_name):
                        self.config.add_section(section_name)

                    for option, value in installer_config.items(section_name):
                        self.config.set(section_name, option, value)

                print(f"Configuration serveur de l'installateur chargée depuis: {installer_config_path}")

        except Exception as e:
            print(f"Erreur lors du chargement de la configuration installateur: {e}")
            # Continuer avec la configuration existante

    def get(self, section: str, option: str, fallback: Any = None) -> str:
        """
        Récupère une valeur de configuration

        Args:
            section: Nom de la section
            option: Nom de l'option
            fallback: Valeur par défaut si non trouvée

        Returns:
            str: Valeur de configuration
        """
        return self.config.get(section, option, fallback=fallback)

    def getboolean(self, section: str, option: str, fallback: bool = False) -> bool:
        """
        Récupère une valeur booléenne de configuration

        Args:
            section: Nom de la section
            option: Nom de l'option
            fallback: Valeur par défaut si non trouvée

        Returns:
            bool: Valeur booléenne
        """
        return self.config.getboolean(section, option, fallback=fallback)

    def getint(self, section: str, option: str, fallback: int = 0) -> int:
        """
        Récupère une valeur entière de configuration

        Args:
            section: Nom de la section
            option: Nom de l'option
            fallback: Valeur par défaut si non trouvée

        Returns:
            int: Valeur entière
        """
        return self.config.getint(section, option, fallback=fallback)

    def set(self, section: str, option: str, value: str):
        """
        Définit une valeur de configuration

        Args:
            section: Nom de la section
            option: Nom de l'option
            value: Nouvelle valeur
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))

    def save(self):
        """
        Sauvegarde la configuration dans le fichier

        Crée les dossiers parents si nécessaire.
        """
        try:
            # Créer le dossier parent si nécessaire
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            # Sauvegarder la configuration
            with open(self.config_file, 'w') as f:
                self.config.write(f)

            print(f"Configuration sauvegardée dans: {self.config_file}")

        except Exception as e:
            print(f"Erreur lors de la sauvegarde de la configuration: {e}")

    def get_server_config(self) -> Dict[str, Any]:
        """
        Récupère la configuration complète du serveur

        Returns:
            dict: Configuration serveur
        """
        return {
            'url': self.get('server', 'url'),
            'auth_token': self.get('server', 'auth_token'),
            'timeout': self.getint('server', 'timeout', 30),
            'verify_ssl': self.getboolean('server', 'verify_ssl', True)
        }

    def get_agent_config(self) -> Dict[str, Any]:
        """
        Récupère la configuration complète de l'agent

        Returns:
            dict: Configuration agent
        """
        return {
            'reporting_frequency': self.get('agent', 'reporting_frequency', 'daily'),
            'log_level': self.get('agent', 'log_level', 'INFO'),
            'collect_software': self.getboolean('agent', 'collect_software', True),
            'collect_hardware': self.getboolean('agent', 'collect_hardware', True),
            'collect_network': self.getboolean('agent', 'collect_network', True)
        }

    def get_web_config(self) -> Dict[str, Any]:
        """
        Récupère la configuration complète de l'interface web

        Returns:
            dict: Configuration interface web
        """
        return {
            'enabled': self.getboolean('web_interface', 'enabled', True),
            'port': self.getint('web_interface', 'port', 18743),
            'host': self.get('web_interface', 'host', '127.0.0.1')
        }

    def validate(self) -> bool:
        """
        Valide la configuration courante

        Returns:
            bool: True si la configuration est valide, False sinon
        """
        errors = []

        # Valider l'URL du serveur
        server_url = self.get('server', 'url')
        if not server_url or not server_url.startswith(('http://', 'https://')):
            errors.append("URL serveur invalide")

        # Valider la fréquence de rapport
        frequency = self.get('agent', 'reporting_frequency')
        if frequency not in ['daily', 'weekly', 'monthly']:
            errors.append("Fréquence de rapport invalide (doit être: daily, weekly, monthly)")

        # Valider le niveau de log
        log_level = self.get('agent', 'log_level')
        if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            errors.append("Niveau de log invalide")

        # Valider le port web
        web_port = self.getint('web_interface', 'port')
        if not (1 <= web_port <= 65535):
            errors.append("Port interface web invalide (doit être entre 1 et 65535)")

        if errors:
            for error in errors:
                print(f"Erreur de configuration: {error}")
            return False

        return True


# Fonction utilitaire pour créer une configuration par défaut
def create_default_config(config_path: str) -> AgentConfig:
    """
    Crée un fichier de configuration par défaut

    Args:
        config_path: Chemin où créer le fichier de configuration

    Returns:
        AgentConfig: Instance de configuration créée
    """
    config = AgentConfig(config_path)
    config.save()
    return config