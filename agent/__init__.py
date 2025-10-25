"""
Watchman Agent Client - Système de collecte d'inventaire multi-plateforme

Ce module principal fournit un agent d'inventaire qui collecte automatiquement
les informations système (matériel, logiciels, réseau) et les envoie à un serveur central.

Author: Watchman Agent Client Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Watchman Agent Client Team"

# Imports principaux pour faciliter l'utilisation
from .core.collector import InventoryCollector
from .core.config import AgentConfig
from .core.logger import AgentLogger

__all__ = ['InventoryCollector', 'AgentConfig', 'AgentLogger']