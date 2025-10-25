"""
Module collecteur principal pour l'agent d'inventaire

Ce module orchestre la collecte de toutes les informations système :
- Coordination des différents collecteurs spécialisés
- Assemblage des données en format unifié
- Gestion des erreurs de collecte
- Optimisation des performances
"""

import os
import sys
import time
import platform
from datetime import datetime
from typing import Dict, Any, List, Optional
import socket
import uuid


class InventoryCollector:
    """
    Collecteur principal qui orchestre toute la collecte d'inventaire

    Cette classe coordonne tous les collecteurs spécialisés et assemble
    les données en un format JSON uniforme pour l'envoi au serveur.
    """

    def __init__(self, config, logger):
        """
        Initialise le collecteur principal

        Args:
            config: Instance de AgentConfig
            logger: Instance de AgentLogger
        """
        self.config = config
        self.logger = logger.get_logger()

        # Configuration de collecte
        agent_config = config.get_agent_config()
        self.collect_software = agent_config['collect_software']
        self.collect_hardware = agent_config['collect_hardware']
        self.collect_network = agent_config['collect_network']

        # Collecteurs spécialisés (seront initialisés à la demande)
        self._system_collector = None
        self._hardware_collector = None
        self._software_collector = None
        self._network_collector = None
        self._platform_collector = None

        # Cache des données collectées
        self._last_collection = None
        self._last_collection_time = None

        self.logger.info("InventoryCollector initialisé")
        self.logger.info(f"Collecte logiciels: {self.collect_software}")
        self.logger.info(f"Collecte matériel: {self.collect_hardware}")
        self.logger.info(f"Collecte réseau: {self.collect_network}")

    def collect_all(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Lance la collecte complète d'inventaire

        Args:
            force_refresh: Force une nouvelle collecte même si cache valide

        Returns:
            dict: Données d'inventaire complètes au format JSON
        """
        start_time = time.time()
        self.logger.info("=== Début de collecte d'inventaire complète ===")

        try:
            # Vérifier si on peut utiliser le cache
            if not force_refresh and self._is_cache_valid():
                self.logger.info("Utilisation du cache de collecte")
                return self._last_collection

            # Structure de base de l'inventaire
            inventory = {
                'assets': [{
                    # Métadonnées de collecte
                    'collection_timestamp': datetime.now().isoformat(),
                    'agent_version': '1.0.0',
                    'collection_duration_seconds': None,  # Sera mis à jour à la fin

                    # Informations système de base
                    'computer_glpi_id': self._generate_computer_id(),
                    'hostname': self._get_hostname(),
                    'architecture': self._get_architecture(),
                    'os': self._get_os_info(),

                    # Informations réseau principales
                    'ip': self._get_primary_ip(),
                    'mac': self._get_primary_mac(),

                    # Informations machine hôte (pour VMs)
                    'host_machine': '',
                    'host_machine_hostname': '',
                    'host_machine_os': '',
                    'host_machine_architecture': '',
                    'host_machine_mac': '',

                    # Collections spécialisées
                    'applications': [],
                    'hardware': {},
                    'network_interfaces': [],
                    'system_info': {}
                }]
            }

            asset = inventory['assets'][0]

            # Collecte système de base
            self.logger.info("Collecte des informations système...")
            system_info = self._collect_system_info()
            asset['system_info'].update(system_info)

            # Collecte matériel (si activée)
            if self.collect_hardware:
                self.logger.info("Collecte des informations matériel...")
                hardware_info = self._collect_hardware_info()
                asset['hardware'].update(hardware_info)

            # Collecte logiciels (si activée)
            if self.collect_software:
                self.logger.info("Collecte des logiciels installés...")
                software_list = self._collect_software_info()
                self.logger.info(f"Logiciels trouvés... {len(software_list)} ")
                asset['applications'].extend(software_list)

            # Collecte réseau (si activée)
            if self.collect_network:
                self.logger.info("Collecte des informations réseau...")
                network_interfaces = self._collect_network_info()
                asset['network_interfaces'].extend(network_interfaces)

            # Collecte spécifique à la plateforme
            self.logger.info("Collecte des informations spécifiques à la plateforme...")
            platform_info = self._collect_platform_specific()
            if platform_info:
                asset['system_info'].update(platform_info)

            # Calculer la durée de collecte
            collection_duration = time.time() - start_time
            asset['collection_duration_seconds'] = round(collection_duration, 2)

            # Mettre en cache
            self._last_collection = inventory
            self._last_collection_time = datetime.now()

            self.logger.info(f"Collecte terminée en {collection_duration:.2f} secondes")
            self.logger.info(f"Collecté: {len(asset['applications'])} applications, "
                           f"{len(asset['network_interfaces'])} interfaces réseau")

            return inventory

        except Exception as e:
            self.logger.exception("Erreur lors de la collecte d'inventaire")
            raise

    def _is_cache_valid(self, cache_duration_minutes: int = 5) -> bool:
        """
        Vérifie si le cache de collecte est encore valide

        Args:
            cache_duration_minutes: Durée de validité du cache en minutes

        Returns:
            bool: True si le cache est valide
        """
        if not self._last_collection or not self._last_collection_time:
            return False

        time_diff = datetime.now() - self._last_collection_time
        return time_diff.total_seconds() < (cache_duration_minutes * 60)

    def _generate_computer_id(self) -> int:
        """
        Génère un ID unique pour cet ordinateur

        Returns:
            int: ID unique basé sur le hostname et MAC
        """
        try:
            # Utiliser hostname + MAC principale pour générer un ID stable
            hostname = socket.gethostname()
            mac = self._get_primary_mac()
            unique_string = f"{hostname}_{mac}"

            # Convertir en hash numérique
            computer_id = abs(hash(unique_string)) % 999999
            return computer_id

        except Exception:
            # Fallback: utiliser un ID basé sur le hostname seul
            hostname = socket.gethostname()
            return abs(hash(hostname)) % 999999

    def _get_hostname(self) -> str:
        """Récupère le nom d'hôte de la machine"""
        try:
            return socket.gethostname()
        except Exception as e:
            self.logger.warning(f"Impossible de récupérer le hostname: {e}")
            return "Unknown"

    def _get_architecture(self) -> str:
        """Récupère l'architecture du processeur"""
        try:
            machine = platform.machine()
            if machine in ['x86_64', 'AMD64']:
                return '64-bit'
            elif machine in ['i386', 'i686', 'x86']:
                return '32-bit'
            else:
                return f"{machine} ({platform.architecture()[0]})"
        except Exception as e:
            self.logger.warning(f"Impossible de récupérer l'architecture: {e}")
            return "Unknown"

    def _get_os_info(self) -> str:
        """Récupère les informations détaillées du système d'exploitation"""
        try:
            if sys.platform == "win32":
                # Windows
                import platform
                return f"{platform.system()} {platform.release()} {platform.version()}"

            elif sys.platform == "darwin":
                # macOS
                import platform
                mac_version = platform.mac_ver()[0]
                return f"macOS {mac_version}"

            else:
                # Linux et autres Unix
                try:
                    # Essayer de lire /etc/os-release
                    with open('/etc/os-release', 'r') as f:
                        lines = f.readlines()

                    os_info = {}
                    for line in lines:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            os_info[key] = value.strip('"')

                    if 'PRETTY_NAME' in os_info:
                        return os_info['PRETTY_NAME']
                    elif 'NAME' in os_info and 'VERSION' in os_info:
                        return f"{os_info['NAME']} {os_info['VERSION']}"

                except FileNotFoundError:
                    pass

                # Fallback pour Linux
                return f"{platform.system()} {platform.release()}"

        except Exception as e:
            self.logger.warning(f"Impossible de récupérer les infos OS: {e}")
            return f"{platform.system()} {platform.release()}"

    def _get_primary_ip(self) -> str:
        """Récupère l'adresse IP principale de la machine"""
        try:
            # Méthode rapide: connexion UDP vers un serveur externe
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                return ip

        except Exception:
            try:
                # Fallback: utiliser hostname
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                return ip

            except Exception as e:
                self.logger.warning(f"Impossible de récupérer l'IP principale: {e}")
                return "127.0.0.1"

    def _get_primary_mac(self) -> str:
        """Récupère l'adresse MAC de l'interface réseau principale"""
        try:
            # Utiliser l'UUID du nœud (basé sur MAC)
            mac_int = uuid.getnode()
            mac_hex = f"{mac_int:012x}"

            # Formatter en MAC address standard
            mac_formatted = ":".join([mac_hex[i:i+2] for i in range(0, 12, 2)])
            return mac_formatted

        except Exception as e:
            self.logger.warning(f"Impossible de récupérer la MAC principale: {e}")
            return "00:00:00:00:00:00"

    def _collect_system_info(self) -> Dict[str, Any]:
        """
        Collecte les informations système générales

        Returns:
            dict: Informations système
        """
        try:
            # Importer le collecteur système
            from ..collectors.system import SystemCollector

            if not self._system_collector:
                self._system_collector = SystemCollector(self.config, self.logger)

            return self._system_collector.collect()

        except Exception as e:
            self.logger.error(f"Erreur collecte système: {e}")
            return {}

    def _collect_hardware_info(self) -> Dict[str, Any]:
        """
        Collecte les informations matériel

        Returns:
            dict: Informations matériel
        """
        if not self.collect_hardware:
            return {}

        try:
            from ..collectors.hardware import HardwareCollector

            if not self._hardware_collector:
                self._hardware_collector = HardwareCollector(self.config, self.logger)

            return self._hardware_collector.collect()

        except Exception as e:
            self.logger.error(f"Erreur collecte matériel: {e}")
            return {}

    def _collect_software_info(self) -> List[Dict[str, Any]]:
        """
        Collecte la liste des logiciels installés

        Returns:
            list: Liste des applications installées
        """
        if not self.collect_software:
            return []

        try:
            from ..collectors.software import SoftwareCollector

            if not self._software_collector:
                self._software_collector = SoftwareCollector(self.config, self.logger)

            return self._software_collector.collect()

        except Exception as e:
            self.logger.error(f"Erreur collecte logiciels: {e}")
            return []

    def _collect_network_info(self) -> List[Dict[str, Any]]:
        """
        Collecte les informations réseau

        Returns:
            list: Liste des interfaces réseau
        """
        if not self.collect_network:
            return []

        try:
            from ..collectors.network import NetworkCollector

            if not self._network_collector:
                self._network_collector = NetworkCollector(self.config, self.logger)

            return self._network_collector.collect()

        except Exception as e:
            self.logger.error(f"Erreur collecte réseau: {e}")
            return []

    def _collect_platform_specific(self) -> Dict[str, Any]:
        """
        Collecte les informations spécifiques à la plateforme

        Returns:
            dict: Informations spécifiques à la plateforme
        """
        try:
            if sys.platform == "win32":
                from ..collectors.platform.windows import WindowsCollector
                collector_class = WindowsCollector

            elif sys.platform == "darwin":
                from ..collectors.platform.macos import MacOSCollector
                collector_class = MacOSCollector

            else:
                from ..collectors.platform.linux import LinuxCollector
                collector_class = LinuxCollector

            if not self._platform_collector:
                self._platform_collector = collector_class(self.config, self.logger)

            return self._platform_collector.collect()

        except Exception as e:
            self.logger.error(f"Erreur collecte spécifique plateforme: {e}")
            return {}

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la dernière collecte

        Returns:
            dict: Statistiques de collecte
        """
        if not self._last_collection:
            return {'status': 'no_collection_yet'}

        asset = self._last_collection['assets'][0]

        return {
            'status': 'success',
            'last_collection_time': self._last_collection_time.isoformat(),
            'collection_duration': asset.get('collection_duration_seconds', 0),
            'applications_count': len(asset.get('applications', [])),
            'network_interfaces_count': len(asset.get('network_interfaces', [])),
            'hardware_components': len(asset.get('hardware', {})),
            'cache_valid': self._is_cache_valid()
        }

    def clear_cache(self):
        """Vide le cache de collecte pour forcer une nouvelle collecte"""
        self._last_collection = None
        self._last_collection_time = None
        self.logger.info("Cache de collecte vidé")