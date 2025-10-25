"""
Module de logging pour l'agent d'inventaire

Ce module fournit un système de logging centralisé avec :
- Rotation automatique des logs
- Différents niveaux de log
- Formatage cohérent
- Support multi-plateforme
"""

import os
import sys
import logging
import logging.handlers
from typing import Optional
from pathlib import Path


class AgentLogger:
    """
    Gestionnaire de logging pour l'agent d'inventaire

    Cette classe configure et gère le système de logging pour l'ensemble
    de l'application, avec rotation automatique et formatage approprié.
    """

    def __init__(self, config=None):
        """
        Initialise le système de logging

        Args:
            config: Instance de AgentConfig pour récupérer les paramètres de log
        """
        self.config = config
        self.logger = logging.getLogger('WatchmanAgentClient')

        # Éviter la duplication si déjà configuré
        if not self.logger.handlers:
            self._setup_logging()

    def _setup_logging(self):
        """
        Configure le système de logging avec les handlers appropriés

        Configure :
        - Le niveau de log basé sur la configuration
        - Le formatage des messages
        - La rotation des fichiers de log
        - La sortie console pour le développement
        """
        # Déterminer le niveau de log
        if self.config:
            log_level_str = self.config.get('agent', 'log_level', 'INFO')
            log_file = self.config.get('logging', 'log_file')
            max_size = self.config.getint('logging', 'max_log_size', 10485760)  # 10MB
            backup_count = self.config.getint('logging', 'backup_count', 5)
        else:
            log_level_str = 'INFO'
            log_file = self._get_default_log_file()
            max_size = 10485760  # 10MB
            backup_count = 5

        # Convertir le niveau de log string en constante logging
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        self.logger.setLevel(log_level)

        # Format des messages de log
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Handler pour fichier avec rotation
        try:
            # Créer le dossier de log si nécessaire
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # Handler avec rotation automatique
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        except Exception as e:
            print(f"Erreur lors de la configuration du logging fichier: {e}")

        # Handler pour la console (utile en développement)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # Format simplifié pour la console
        console_formatter = logging.Formatter(
            fmt='%(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Message de démarrage
        self.logger.info("Système de logging initialisé")
        if self.config:
            self.logger.info(f"Niveau de log: {log_level_str}")
            self.logger.info(f"Fichier de log: {log_file}")

    def _get_default_log_file(self) -> str:
        """
        Détermine le fichier de log par défaut selon la plateforme

        Returns:
            str: Chemin vers le fichier de log par défaut
        """
        if sys.platform == "win32":
            return os.path.join(
                os.environ.get("TEMP", "C:\\temp"),
                "watchman-agent-client.log"
            )
        else:
            return "/tmp/watchman-agent-client.log"

    def get_logger(self) -> logging.Logger:
        """
        Retourne l'instance du logger

        Returns:
            logging.Logger: Instance du logger configuré
        """
        return self.logger

    def debug(self, message: str):
        """Log un message de niveau DEBUG"""
        self.logger.debug(message)

    def info(self, message: str):
        """Log un message de niveau INFO"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log un message de niveau WARNING"""
        self.logger.warning(message)

    def error(self, message: str):
        """Log un message de niveau ERROR"""
        self.logger.error(message)

    def critical(self, message: str):
        """Log un message de niveau CRITICAL"""
        self.logger.critical(message)

    def exception(self, message: str):
        """
        Log une exception avec sa stack trace

        Args:
            message: Message descriptif de l'erreur
        """
        self.logger.exception(message)

    def log_system_info(self):
        """
        Log les informations système de base au démarrage

        Utile pour le diagnostic et le debug
        """
        self.info(f"Plateforme: {sys.platform}")
        self.info(f"Version Python: {sys.version}")
        self.info(f"Répertoire de travail: {os.getcwd()}")

        # Informations sur l'utilisateur courant
        try:
            import getpass
            self.info(f"Utilisateur: {getpass.getuser()}")
        except Exception:
            self.info("Utilisateur: Non déterminé")

    def log_config_info(self, config):
        """
        Log les informations de configuration (sans les données sensibles)

        Args:
            config: Instance de AgentConfig
        """
        self.info("=== Configuration de l'agent ===")

        # Configuration agent (sans token)
        agent_config = config.get_agent_config()
        for key, value in agent_config.items():
            self.info(f"Agent.{key}: {value}")

        # Configuration web
        web_config = config.get_web_config()
        for key, value in web_config.items():
            self.info(f"Web.{key}: {value}")

        # Configuration serveur (sans token pour sécurité)
        server_config = config.get_server_config()
        for key, value in server_config.items():
            if key == 'auth_token':
                # Ne pas logger le token complet pour sécurité
                token_preview = value[:8] + "..." if len(value) > 8 else "Non configuré"
                self.info(f"Server.{key}: {token_preview}")
            else:
                self.info(f"Server.{key}: {value}")

        self.info("=== Fin configuration ===")


def get_logger(name: str = "WatchmanAgentClient") -> logging.Logger:
    """
    Fonction utilitaire pour récupérer un logger nommé

    Args:
        name: Nom du logger

    Returns:
        logging.Logger: Instance du logger
    """
    return logging.getLogger(name)