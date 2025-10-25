"""
Collecteur d'informations réseau pour l'agent d'inventaire

Ce module collecte les informations réseau complètes :
- Interfaces réseau (Ethernet, WiFi, etc.)
- Adresses IP (IPv4 et IPv6)
- Adresses MAC
- Statistiques de trafic
- Configuration DNS
- Routes réseau
"""

import sys
import socket
import psutil
from typing import List, Dict, Any

from .base import BaseCollector


class NetworkCollector(BaseCollector):
    """
    Collecteur d'informations réseau détaillées

    Ce collecteur utilise psutil et des commandes système spécifiques
    pour récupérer toutes les informations réseau de la machine.
    """

    def collect(self) -> List[Dict[str, Any]]:
        """
        Collecte toutes les informations réseau

        Returns:
            list: Liste des interfaces réseau avec leurs détails
        """
        self._start_collection()

        interfaces = []

        # Récupérer toutes les interfaces réseau
        network_interfaces = self._safe_execute(
            lambda: psutil.net_if_addrs(),
            "Erreur récupération interfaces réseau",
            {}
        )

        # Statistiques des interfaces
        interface_stats = self._safe_execute(
            lambda: psutil.net_if_stats(),
            "Erreur récupération statistiques interfaces",
            {}
        )

        # Statistiques de trafic
        traffic_stats = self._safe_execute(
            lambda: psutil.net_io_counters(pernic=True),
            "Erreur récupération statistiques trafic",
            {}
        )

        # Traiter chaque interface
        for interface_name, addresses in network_interfaces.items():
            interface_info = {
                'name': interface_name,
                'addresses': [],
                'mac_address': None,
                'is_up': False,
                'is_running': False,
                'speed_mbps': None,
                'mtu': None,
                'traffic_stats': {},
                'type': self._detect_interface_type(interface_name)
            }

            # Traiter les adresses de l'interface
            for addr in addresses:
                addr_info = {
                    'family': addr.family.name if hasattr(addr.family, 'name') else str(addr.family),
                    'address': addr.address,
                    'netmask': addr.netmask,
                    'broadcast': addr.broadcast,
                    'ptp': addr.ptp  # Point-to-point
                }

                # Déterminer le type d'adresse
                if addr.family == socket.AF_INET:
                    addr_info['type'] = 'IPv4'
                elif addr.family == socket.AF_INET6:
                    addr_info['type'] = 'IPv6'
                elif addr.family == psutil.AF_LINK:
                    addr_info['type'] = 'MAC'
                    # Stocker l'adresse MAC principale
                    if not interface_info['mac_address']:
                        interface_info['mac_address'] = addr.address
                else:
                    addr_info['type'] = 'Other'

                interface_info['addresses'].append(addr_info)

            # Statistiques de l'interface
            if interface_name in interface_stats:
                stats = interface_stats[interface_name]
                interface_info['is_up'] = stats.isup
                interface_info['speed_mbps'] = stats.speed if stats.speed > 0 else None
                interface_info['mtu'] = stats.mtu

            # Statistiques de trafic
            if interface_name in traffic_stats:
                traffic = traffic_stats[interface_name]
                interface_info['traffic_stats'] = {
                    'bytes_sent': traffic.bytes_sent,
                    'bytes_sent_formatted': self._format_bytes(traffic.bytes_sent),
                    'bytes_recv': traffic.bytes_recv,
                    'bytes_recv_formatted': self._format_bytes(traffic.bytes_recv),
                    'packets_sent': traffic.packets_sent,
                    'packets_recv': traffic.packets_recv,
                    'errors_in': traffic.errin,
                    'errors_out': traffic.errout,
                    'drops_in': traffic.dropin,
                    'drops_out': traffic.dropout
                }

            # Informations spécifiques à la plateforme
            platform_info = self._get_platform_interface_info(interface_name)
            interface_info.update(platform_info)

            interfaces.append(interface_info)

        # Trier les interfaces (interfaces principales en premier)
        interfaces = self._sort_interfaces(interfaces)

        # Ajouter les informations réseau globales
        global_network_info = self._collect_global_network_info()

        self.logger.info(f"Collecté {len(interfaces)} interfaces réseau")
        self.last_collection_duration = self._end_collection()

        return interfaces

    def _detect_interface_type(self, interface_name: str) -> str:
        """
        Détecte le type d'interface réseau

        Args:
            interface_name: Nom de l'interface

        Returns:
            str: Type d'interface (ethernet, wifi, loopback, etc.)
        """
        name_lower = interface_name.lower()

        # Patterns communs pour détecter le type
        if name_lower in ['lo', 'lo0']:
            return 'loopback'
        elif 'eth' in name_lower or 'enp' in name_lower or 'eno' in name_lower:
            return 'ethernet'
        elif 'wlan' in name_lower or 'wifi' in name_lower or 'wlp' in name_lower:
            return 'wifi'
        elif 'ppp' in name_lower:
            return 'ppp'
        elif 'tun' in name_lower or 'tap' in name_lower:
            return 'vpn'
        elif 'docker' in name_lower or 'br-' in name_lower:
            return 'bridge'
        elif 'vbox' in name_lower or 'vmware' in name_lower:
            return 'virtual'
        elif sys.platform == "win32":
            # Windows - patterns spécifiques
            if 'local area connection' in name_lower or 'ethernet' in name_lower:
                return 'ethernet'
            elif 'wireless' in name_lower or 'wi-fi' in name_lower:
                return 'wifi'
            elif 'bluetooth' in name_lower:
                return 'bluetooth'
        else:
            return 'unknown'

    def _get_platform_interface_info(self, interface_name: str) -> Dict[str, Any]:
        """
        Récupère les informations spécifiques à la plateforme pour une interface

        Args:
            interface_name: Nom de l'interface

        Returns:
            dict: Informations spécifiques à la plateforme
        """
        platform_info = {}

        if sys.platform == "win32":
            platform_info.update(self._get_windows_interface_info(interface_name))
        elif sys.platform == "linux":
            platform_info.update(self._get_linux_interface_info(interface_name))
        elif sys.platform == "darwin":
            platform_info.update(self._get_macos_interface_info(interface_name))

        return platform_info

    def _get_windows_interface_info(self, interface_name: str) -> Dict[str, Any]:
        """
        Informations interface Windows via WMI

        Args:
            interface_name: Nom de l'interface

        Returns:
            dict: Informations interface Windows
        """
        interface_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Rechercher l'adaptateur réseau correspondant
            for adapter in c.Win32_NetworkAdapter():
                if adapter.NetConnectionID == interface_name or adapter.Name == interface_name:
                    interface_info['manufacturer'] = self._clean_string(adapter.Manufacturer)
                    interface_info['description'] = self._clean_string(adapter.Description)
                    interface_info['device_id'] = self._clean_string(adapter.DeviceID)
                    interface_info['adapter_type'] = self._clean_string(adapter.AdapterType)
                    interface_info['physical_adapter'] = adapter.PhysicalAdapter
                    break

            # Informations de configuration
            for config in c.Win32_NetworkAdapterConfiguration():
                if config.Description and interface_name in config.Description:
                    interface_info['dhcp_enabled'] = config.DHCPEnabled
                    interface_info['dns_servers'] = list(config.DNSServerSearchOrder) if config.DNSServerSearchOrder else []
                    interface_info['gateway'] = list(config.DefaultIPGateway) if config.DefaultIPGateway else []
                    interface_info['domain'] = self._clean_string(config.DNSDomain)
                    break

        except ImportError:
            self.logger.debug("Module WMI non disponible pour interface réseau")
        except Exception as e:
            self.logger.debug(f"Erreur récupération interface Windows {interface_name}: {e}")

        return interface_info

    def _get_linux_interface_info(self, interface_name: str) -> Dict[str, Any]:
        """
        Informations interface Linux

        Args:
            interface_name: Nom de l'interface

        Returns:
            dict: Informations interface Linux
        """
        interface_info = {}

        try:
            # Informations depuis /sys/class/net
            sys_path = f"/sys/class/net/{interface_name}"

            # Vitesse de l'interface
            speed_file = f"{sys_path}/speed"
            speed = self._read_file(speed_file)
            if speed and speed.isdigit():
                interface_info['speed_mbps'] = int(speed)

            # Duplex
            duplex_file = f"{sys_path}/duplex"
            duplex = self._read_file(duplex_file)
            if duplex:
                interface_info['duplex'] = duplex

            # État opérationnel
            operstate_file = f"{sys_path}/operstate"
            operstate = self._read_file(operstate_file)
            if operstate:
                interface_info['operational_state'] = operstate
                interface_info['is_running'] = operstate == 'up'

            # Type d'interface
            type_file = f"{sys_path}/type"
            if_type = self._read_file(type_file)
            if if_type:
                interface_info['interface_type_id'] = int(if_type) if if_type.isdigit() else None

            # Driver utilisé
            driver_path = f"{sys_path}/device/driver"
            try:
                import os
                if os.path.islink(driver_path):
                    driver = os.path.basename(os.readlink(driver_path))
                    interface_info['driver'] = driver
            except Exception:
                pass

        except Exception as e:
            self.logger.debug(f"Erreur récupération interface Linux {interface_name}: {e}")

        return interface_info

    def _get_macos_interface_info(self, interface_name: str) -> Dict[str, Any]:
        """
        Informations interface macOS

        Args:
            interface_name: Nom de l'interface

        Returns:
            dict: Informations interface macOS
        """
        interface_info = {}

        try:
            # Utiliser ifconfig pour récupérer des détails
            output = self._execute_command(f"ifconfig {interface_name}")
            if output:
                # Parser la sortie ifconfig
                for line in output.split('\n'):
                    line = line.strip()
                    if 'media:' in line:
                        interface_info['media'] = line.split('media:', 1)[1].strip()
                    elif 'status:' in line:
                        status = line.split('status:', 1)[1].strip()
                        interface_info['status'] = status
                        interface_info['is_running'] = status == 'active'

        except Exception as e:
            self.logger.debug(f"Erreur récupération interface macOS {interface_name}: {e}")

        return interface_info

    def _sort_interfaces(self, interfaces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Trie les interfaces par priorité

        Args:
            interfaces: Liste des interfaces

        Returns:
            list: Interfaces triées
        """
        def interface_priority(interface):
            """Détermine la priorité d'une interface pour le tri"""
            name = interface['name'].lower()
            interface_type = interface.get('type', 'unknown')

            # Priorité basée sur le type et l'état
            if interface_type == 'loopback':
                return 100  # Loopback en dernier
            elif not interface.get('is_up', False):
                return 90  # Interfaces inactives
            elif interface_type == 'ethernet':
                return 10  # Ethernet en premier
            elif interface_type == 'wifi':
                return 20  # WiFi en second
            else:
                return 50  # Autres au milieu

        return sorted(interfaces, key=interface_priority)

    def _collect_global_network_info(self) -> Dict[str, Any]:
        """
        Collecte les informations réseau globales

        Returns:
            dict: Informations réseau globales
        """
        global_info = {
            'hostname': self._get_hostname(),
            'fqdn': self._get_fqdn(),
            'dns_servers': self._get_dns_servers(),
            'default_gateway': self._get_default_gateway(),
            'routing_table': self._get_routing_table(),
            'connections': self._get_network_connections()
        }

        return global_info

    def _get_hostname(self) -> str:
        """Récupère le hostname de la machine"""
        try:
            return socket.gethostname()
        except Exception as e:
            self.logger.warning(f"Erreur récupération hostname: {e}")
            return "Unknown"

    def _get_fqdn(self) -> str:
        """Récupère le FQDN (Fully Qualified Domain Name)"""
        try:
            return socket.getfqdn()
        except Exception as e:
            self.logger.warning(f"Erreur récupération FQDN: {e}")
            return "Unknown"

    def _get_dns_servers(self) -> List[str]:
        """
        Récupère la liste des serveurs DNS configurés

        Returns:
            list: Liste des serveurs DNS
        """
        dns_servers = []

        if sys.platform == "win32":
            dns_servers = self._get_windows_dns_servers()
        elif sys.platform == "linux":
            dns_servers = self._get_linux_dns_servers()
        elif sys.platform == "darwin":
            dns_servers = self._get_macos_dns_servers()

        return dns_servers

    def _get_windows_dns_servers(self) -> List[str]:
        """Récupère les serveurs DNS Windows"""
        dns_servers = []

        try:
            import wmi
            c = wmi.WMI()

            for config in c.Win32_NetworkAdapterConfiguration():
                if config.DNSServerSearchOrder:
                    dns_servers.extend(config.DNSServerSearchOrder)

        except Exception as e:
            self.logger.debug(f"Erreur récupération DNS Windows: {e}")

        return list(set(dns_servers))  # Supprimer les doublons

    def _get_linux_dns_servers(self) -> List[str]:
        """Récupère les serveurs DNS Linux"""
        dns_servers = []

        try:
            # Lire /etc/resolv.conf
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('nameserver'):
                        parts = line.split()
                        if len(parts) >= 2:
                            dns_servers.append(parts[1])

        except FileNotFoundError:
            self.logger.debug("/etc/resolv.conf non trouvé")
        except Exception as e:
            self.logger.debug(f"Erreur lecture /etc/resolv.conf: {e}")

        return dns_servers

    def _get_macos_dns_servers(self) -> List[str]:
        """Récupère les serveurs DNS macOS"""
        dns_servers = []

        try:
            output = self._execute_command("scutil --dns | grep nameserver")
            if output:
                for line in output.split('\n'):
                    if 'nameserver' in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            dns_servers.append(parts[2])

        except Exception as e:
            self.logger.debug(f"Erreur récupération DNS macOS: {e}")

        return dns_servers

    def _get_default_gateway(self) -> List[str]:
        """
        Récupère la passerelle par défaut

        Returns:
            list: Liste des passerelles par défaut
        """
        gateways = []

        try:
            # Utiliser psutil pour récupérer les gateways
            if hasattr(psutil, 'net_if_addrs'):
                # Méthode alternative via commandes système
                if sys.platform == "win32":
                    output = self._execute_command("route print 0.0.0.0")
                    # Parser la sortie pour extraire la gateway
                elif sys.platform == "linux":
                    output = self._execute_command("ip route show default")
                    if output:
                        for line in output.split('\n'):
                            if 'default via' in line:
                                parts = line.split()
                                if len(parts) >= 3:
                                    gateways.append(parts[2])
                elif sys.platform == "darwin":
                    output = self._execute_command("route -n get default")
                    if output:
                        for line in output.split('\n'):
                            if 'gateway:' in line:
                                gateway = line.split(':', 1)[1].strip()
                                if gateway:
                                    gateways.append(gateway)

        except Exception as e:
            self.logger.debug(f"Erreur récupération gateway: {e}")

        return gateways

    def _get_routing_table(self) -> List[Dict[str, Any]]:
        """
        Récupère la table de routage (version simplifiée)

        Returns:
            list: Entrées de la table de routage
        """
        routes = []

        try:
            if sys.platform == "linux":
                output = self._execute_command("ip route show")
                if output:
                    for line in output.split('\n'):
                        if line.strip():
                            # Parser basique des routes Linux
                            route_info = {'raw': line.strip()}
                            routes.append(route_info)

        except Exception as e:
            self.logger.debug(f"Erreur récupération table de routage: {e}")

        # Limiter le nombre de routes pour éviter trop de données
        return routes[:20]

    def _get_network_connections(self) -> Dict[str, Any]:
        """
        Récupère les statistiques des connexions réseau

        Returns:
            dict: Statistiques des connexions
        """
        connections_info = {
            'total_connections': 0,
            'by_status': {},
            'by_type': {}
        }

        try:
            connections = psutil.net_connections()

            connections_info['total_connections'] = len(connections)

            # Compter par statut
            for conn in connections:
                status = conn.status if conn.status else 'UNKNOWN'
                connections_info['by_status'][status] = connections_info['by_status'].get(status, 0) + 1

                # Compter par type (TCP/UDP)
                conn_type = 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP'
                connections_info['by_type'][conn_type] = connections_info['by_type'].get(conn_type, 0) + 1

        except Exception as e:
            self.logger.debug(f"Erreur récupération connexions: {e}")

        return connections_info