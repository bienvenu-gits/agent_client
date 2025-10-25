"""
Collecteur d'informations matériel pour l'agent d'inventaire

Ce module collecte les informations matériel détaillées :
- Processeur (CPU)
- Mémoire (RAM)
- Disques de stockage
- Carte graphique
- Carte réseau
- Carte mère et BIOS
"""

import sys
import psutil
from typing import Dict, Any, List

from .base import BaseCollector


class HardwareCollector(BaseCollector):
    """
    Collecteur d'informations matériel détaillées

    Ce collecteur utilise psutil et des API spécifiques à chaque plateforme
    pour récupérer les informations matériel complètes.
    """

    def collect(self) -> Dict[str, Any]:
        """
        Collecte toutes les informations matériel

        Returns:
            dict: Informations matériel complètes
        """
        self._start_collection()

        hardware_info = {
            # Processeur
            'cpu': self._collect_cpu_details(),

            # Mémoire
            'memory': self._collect_memory_details(),

            # Stockage
            'storage': self._collect_storage_details(),

            # Carte graphique
            'graphics': self._collect_graphics_info(),

            # Carte mère et BIOS
            'motherboard': self._collect_motherboard_info(),

            # Informations système générales
            'system': self._collect_system_hardware()
        }

        self.last_collection_duration = self._end_collection()
        return hardware_info

    def _collect_cpu_details(self) -> Dict[str, Any]:
        """
        Collecte les détails avancés du processeur

        Returns:
            dict: Informations CPU détaillées
        """
        cpu_info = {}

        # Informations de base via psutil
        cpu_info['cores_physical'] = self._safe_execute(
            lambda: psutil.cpu_count(logical=False),
            "Erreur récupération cores physiques",
            0
        )

        cpu_info['cores_logical'] = self._safe_execute(
            lambda: psutil.cpu_count(logical=True),
            "Erreur récupération cores logiques",
            0
        )

        # Fréquences
        cpu_freq = self._safe_execute(
            lambda: psutil.cpu_freq(),
            "Erreur récupération fréquence CPU"
        )

        if cpu_freq:
            cpu_info['frequency_current_mhz'] = round(cpu_freq.current, 1)
            cpu_info['frequency_min_mhz'] = round(cpu_freq.min, 1) if cpu_freq.min else None
            cpu_info['frequency_max_mhz'] = round(cpu_freq.max, 1) if cpu_freq.max else None

        # Informations spécifiques à la plateforme
        platform_cpu = self._get_platform_cpu_info()
        cpu_info.update(platform_cpu)

        return cpu_info

    def _get_platform_cpu_info(self) -> Dict[str, Any]:
        """
        Récupère les informations CPU spécifiques à la plateforme

        Returns:
            dict: Informations CPU spécifiques
        """
        cpu_info = {}

        if sys.platform == "win32":
            cpu_info.update(self._get_windows_cpu_info())
        elif sys.platform == "darwin":
            cpu_info.update(self._get_macos_cpu_info())
        else:
            cpu_info.update(self._get_linux_cpu_info())

        return cpu_info

    def _get_windows_cpu_info(self) -> Dict[str, Any]:
        """
        Informations CPU Windows via WMI

        Returns:
            dict: Informations CPU Windows
        """
        cpu_info = {}

        try:
            import wmi
            c = wmi.WMI()

            for processor in c.Win32_Processor():
                cpu_info['name'] = self._clean_string(processor.Name)
                cpu_info['manufacturer'] = self._clean_string(processor.Manufacturer)
                cpu_info['family'] = processor.Family
                cpu_info['model'] = processor.Model
                cpu_info['stepping'] = processor.Stepping
                cpu_info['architecture'] = processor.Architecture
                cpu_info['max_clock_speed_mhz'] = processor.MaxClockSpeed
                cpu_info['current_clock_speed_mhz'] = processor.CurrentClockSpeed
                cpu_info['l2_cache_size_kb'] = processor.L2CacheSize
                cpu_info['l3_cache_size_kb'] = processor.L3CacheSize
                break  # Premier processeur seulement

        except ImportError:
            self.logger.debug("Module WMI non disponible pour CPU")
        except Exception as e:
            self.logger.warning(f"Erreur récupération CPU Windows: {e}")

        return cpu_info

    def _get_macos_cpu_info(self) -> Dict[str, Any]:
        """
        Informations CPU macOS via sysctl

        Returns:
            dict: Informations CPU macOS
        """
        cpu_info = {}

        # Commandes sysctl pour macOS
        sysctl_commands = {
            'name': 'machdep.cpu.brand_string',
            'vendor': 'machdep.cpu.vendor',
            'family': 'machdep.cpu.family',
            'model': 'machdep.cpu.model',
            'stepping': 'machdep.cpu.stepping',
            'cache_size_l1i': 'hw.l1icachesize',
            'cache_size_l1d': 'hw.l1dcachesize',
            'cache_size_l2': 'hw.l2cachesize',
            'cache_size_l3': 'hw.l3cachesize'
        }

        for key, command in sysctl_commands.items():
            value = self._execute_command(f"sysctl -n {command}")
            if value:
                if key.startswith('cache_size_'):
                    try:
                        # Convertir en KB
                        cpu_info[f"{key}_kb"] = int(value) // 1024
                    except ValueError:
                        pass
                else:
                    cpu_info[key] = self._clean_string(value)

        return cpu_info

    def _get_linux_cpu_info(self) -> Dict[str, Any]:
        """
        Informations CPU Linux via /proc/cpuinfo

        Returns:
            dict: Informations CPU Linux
        """
        cpu_info = {}

        try:
            with open('/proc/cpuinfo', 'r') as f:
                lines = f.readlines()

            cpu_data = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    cpu_data[key] = value

            # Mapper les champs importants
            field_mapping = {
                'model name': 'name',
                'vendor_id': 'vendor',
                'cpu family': 'family',
                'model': 'model',
                'stepping': 'stepping',
                'cpu MHz': 'current_clock_speed_mhz',
                'cache size': 'cache_size'
            }

            for proc_key, info_key in field_mapping.items():
                if proc_key in cpu_data:
                    value = cpu_data[proc_key]
                    if info_key == 'current_clock_speed_mhz':
                        try:
                            cpu_info[info_key] = float(value)
                        except ValueError:
                            pass
                    elif info_key in ['family', 'model', 'stepping']:
                        try:
                            cpu_info[info_key] = int(value)
                        except ValueError:
                            pass
                    else:
                        cpu_info[info_key] = self._clean_string(value)

        except FileNotFoundError:
            self.logger.debug("/proc/cpuinfo non trouvé")
        except Exception as e:
            self.logger.warning(f"Erreur lecture /proc/cpuinfo: {e}")

        return cpu_info

    def _collect_memory_details(self) -> Dict[str, Any]:
        """
        Collecte les détails de la mémoire système

        Returns:
            dict: Informations mémoire détaillées
        """
        memory_info = {}

        # Informations de base via psutil
        virtual_mem = self._safe_execute(
            lambda: psutil.virtual_memory(),
            "Erreur récupération mémoire virtuelle"
        )

        if virtual_mem:
            memory_info['total_bytes'] = virtual_mem.total
            memory_info['total_formatted'] = self._format_bytes(virtual_mem.total)
            memory_info['available_bytes'] = virtual_mem.available
            memory_info['available_formatted'] = self._format_bytes(virtual_mem.available)

        # Informations spécifiques à la plateforme
        platform_memory = self._get_platform_memory_info()
        memory_info.update(platform_memory)

        return memory_info

    def _get_platform_memory_info(self) -> Dict[str, Any]:
        """
        Informations mémoire spécifiques à la plateforme

        Returns:
            dict: Informations mémoire détaillées
        """
        memory_info = {}

        if sys.platform == "win32":
            memory_info.update(self._get_windows_memory_info())
        elif sys.platform == "linux":
            memory_info.update(self._get_linux_memory_info())

        return memory_info

    def _get_windows_memory_info(self) -> Dict[str, Any]:
        """
        Informations mémoire Windows via WMI

        Returns:
            dict: Informations mémoire Windows
        """
        memory_info = {
            'modules': []
        }

        try:
            import wmi
            c = wmi.WMI()

            # Informations sur les modules de mémoire
            for memory_module in c.Win32_PhysicalMemory():
                module_info = {
                    'manufacturer': self._clean_string(memory_module.Manufacturer),
                    'part_number': self._clean_string(memory_module.PartNumber),
                    'serial_number': self._clean_string(memory_module.SerialNumber),
                    'capacity_bytes': memory_module.Capacity,
                    'capacity_formatted': self._format_bytes(memory_module.Capacity),
                    'speed_mhz': memory_module.Speed,
                    'memory_type': memory_module.MemoryType,
                    'device_locator': self._clean_string(memory_module.DeviceLocator)
                }
                memory_info['modules'].append(module_info)

        except ImportError:
            self.logger.debug("Module WMI non disponible pour mémoire")
        except Exception as e:
            self.logger.warning(f"Erreur récupération mémoire Windows: {e}")

        return memory_info

    def _get_linux_memory_info(self) -> Dict[str, Any]:
        """
        Informations mémoire Linux via /proc/meminfo

        Returns:
            dict: Informations mémoire Linux
        """
        memory_info = {}

        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()

            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    # Convertir en bytes si c'est en kB
                    if 'kB' in value:
                        try:
                            kb_value = int(value.replace('kB', '').strip())
                            bytes_value = kb_value * 1024
                            memory_info[f"{key.lower()}_bytes"] = bytes_value
                            memory_info[f"{key.lower()}_formatted"] = self._format_bytes(bytes_value)
                        except ValueError:
                            pass

        except FileNotFoundError:
            self.logger.debug("/proc/meminfo non trouvé")
        except Exception as e:
            self.logger.warning(f"Erreur lecture /proc/meminfo: {e}")

        return memory_info

    def _collect_storage_details(self) -> Dict[str, Any]:
        """
        Collecte les détails des dispositifs de stockage

        Returns:
            dict: Informations stockage détaillées
        """
        storage_info = {
            'devices': [],
            'total_capacity_bytes': 0
        }

        # Informations via psutil
        disk_partitions = self._safe_execute(
            lambda: psutil.disk_partitions(),
            "Erreur récupération partitions",
            []
        )

        seen_devices = set()
        total_capacity = 0

        for partition in disk_partitions:
            try:
                # Éviter les doublons de devices
                device_key = partition.device
                if device_key in seen_devices:
                    continue
                seen_devices.add(device_key)

                disk_usage = psutil.disk_usage(partition.mountpoint)

                device_info = {
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'filesystem': partition.fstype,
                    'total_bytes': disk_usage.total,
                    'total_formatted': self._format_bytes(disk_usage.total),
                    'used_bytes': disk_usage.used,
                    'used_formatted': self._format_bytes(disk_usage.used),
                    'free_bytes': disk_usage.free,
                    'free_formatted': self._format_bytes(disk_usage.free),
                    'usage_percent': round((disk_usage.used / disk_usage.total) * 100, 1) if disk_usage.total > 0 else 0
                }

                # Ajouter des informations spécifiques à la plateforme
                platform_storage = self._get_platform_storage_info(partition.device)
                device_info.update(platform_storage)

                storage_info['devices'].append(device_info)
                total_capacity += disk_usage.total

            except PermissionError:
                # Partition non accessible
                pass
            except Exception as e:
                self.logger.warning(f"Erreur traitement device {partition.device}: {e}")

        storage_info['total_capacity_bytes'] = total_capacity
        storage_info['total_capacity_formatted'] = self._format_bytes(total_capacity)

        return storage_info

    def _get_platform_storage_info(self, device: str) -> Dict[str, Any]:
        """
        Informations stockage spécifiques à la plateforme

        Args:
            device: Nom du device

        Returns:
            dict: Informations stockage spécifiques
        """
        storage_info = {}

        if sys.platform == "win32":
            storage_info.update(self._get_windows_storage_info(device))
        elif sys.platform == "linux":
            storage_info.update(self._get_linux_storage_info(device))

        return storage_info

    def _get_windows_storage_info(self, device: str) -> Dict[str, Any]:
        """
        Informations stockage Windows via WMI

        Args:
            device: Nom du device Windows

        Returns:
            dict: Informations stockage Windows
        """
        storage_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Rechercher le disque physique correspondant
            for disk in c.Win32_DiskDrive():
                # Essayer de matcher le device
                if device.replace('\\', '').replace(':', '') in disk.DeviceID.replace('\\', ''):
                    storage_info['model'] = self._clean_string(disk.Model)
                    storage_info['manufacturer'] = self._clean_string(disk.Manufacturer)
                    storage_info['serial_number'] = self._clean_string(disk.SerialNumber)
                    storage_info['interface_type'] = self._clean_string(disk.InterfaceType)
                    storage_info['media_type'] = self._clean_string(disk.MediaType)
                    break

        except ImportError:
            self.logger.debug("Module WMI non disponible pour stockage")
        except Exception as e:
            self.logger.debug(f"Erreur récupération stockage Windows: {e}")

        return storage_info

    def _get_linux_storage_info(self, device: str) -> Dict[str, Any]:
        """
        Informations stockage Linux

        Args:
            device: Nom du device Linux

        Returns:
            dict: Informations stockage Linux
        """
        storage_info = {}

        try:
            # Extraire le nom du device de base (ex: /dev/sda1 -> sda)
            import re
            device_match = re.search(r'/dev/([a-z]+)', device)
            if device_match:
                base_device = device_match.group(1)

                # Lire les informations depuis /sys/block
                sys_path = f"/sys/block/{base_device}"

                # Modèle
                model_file = f"{sys_path}/device/model"
                model = self._read_file(model_file)
                if model:
                    storage_info['model'] = self._clean_string(model)

                # Vendor
                vendor_file = f"{sys_path}/device/vendor"
                vendor = self._read_file(vendor_file)
                if vendor:
                    storage_info['manufacturer'] = self._clean_string(vendor)

                # Type de rotation (SSD vs HDD)
                rotational_file = f"{sys_path}/queue/rotational"
                rotational = self._read_file(rotational_file)
                if rotational:
                    storage_info['is_ssd'] = rotational.strip() == '0'
                    storage_info['media_type'] = 'SSD' if rotational.strip() == '0' else 'HDD'

        except Exception as e:
            self.logger.debug(f"Erreur récupération stockage Linux: {e}")

        return storage_info

    def _collect_graphics_info(self) -> Dict[str, Any]:
        """
        Collecte les informations carte graphique

        Returns:
            dict: Informations carte graphique
        """
        graphics_info = {
            'adapters': []
        }

        if sys.platform == "win32":
            graphics_info['adapters'] = self._get_windows_graphics_info()
        elif sys.platform == "linux":
            graphics_info['adapters'] = self._get_linux_graphics_info()

        return graphics_info

    def _get_windows_graphics_info(self) -> List[Dict[str, Any]]:
        """
        Informations carte graphique Windows via WMI

        Returns:
            list: Liste des adaptateurs graphiques
        """
        adapters = []

        try:
            import wmi
            c = wmi.WMI()

            for adapter in c.Win32_VideoController():
                adapter_info = {
                    'name': self._clean_string(adapter.Name),
                    'manufacturer': self._clean_string(adapter.AdapterCompatibility),
                    'driver_version': self._clean_string(adapter.DriverVersion),
                    'driver_date': adapter.DriverDate,
                    'memory_bytes': adapter.AdapterRAM,
                    'memory_formatted': self._format_bytes(adapter.AdapterRAM) if adapter.AdapterRAM else 'N/A',
                    'device_id': self._clean_string(adapter.DeviceID),
                    'status': self._clean_string(adapter.Status)
                }
                adapters.append(adapter_info)

        except ImportError:
            self.logger.debug("Module WMI non disponible pour graphiques")
        except Exception as e:
            self.logger.warning(f"Erreur récupération graphiques Windows: {e}")

        return adapters

    def _get_linux_graphics_info(self) -> List[Dict[str, Any]]:
        """
        Informations carte graphique Linux via lspci

        Returns:
            list: Liste des adaptateurs graphiques
        """
        adapters = []

        try:
            output = self._execute_command("lspci | grep -i vga")
            if output:
                for line in output.split('\n'):
                    if line.strip():
                        # Parser la ligne lspci
                        parts = line.split(': ', 1)
                        if len(parts) >= 2:
                            adapter_info = {
                                'name': self._clean_string(parts[1]),
                                'bus_info': parts[0],
                                'manufacturer': 'Unknown',
                                'driver_version': 'Unknown'
                            }

                            # Extraire le fabricant du nom
                            name_lower = adapter_info['name'].lower()
                            if 'nvidia' in name_lower:
                                adapter_info['manufacturer'] = 'NVIDIA'
                            elif 'amd' in name_lower or 'ati' in name_lower:
                                adapter_info['manufacturer'] = 'AMD'
                            elif 'intel' in name_lower:
                                adapter_info['manufacturer'] = 'Intel'

                            adapters.append(adapter_info)

        except Exception as e:
            self.logger.debug(f"Erreur récupération graphiques Linux: {e}")

        return adapters

    def _collect_motherboard_info(self) -> Dict[str, Any]:
        """
        Collecte les informations carte mère et BIOS

        Returns:
            dict: Informations carte mère et BIOS
        """
        motherboard_info = {}

        if sys.platform == "win32":
            motherboard_info.update(self._get_windows_motherboard_info())
        elif sys.platform == "linux":
            motherboard_info.update(self._get_linux_motherboard_info())

        return motherboard_info

    def _get_windows_motherboard_info(self) -> Dict[str, Any]:
        """
        Informations carte mère Windows via WMI

        Returns:
            dict: Informations carte mère Windows
        """
        motherboard_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Informations carte mère
            for board in c.Win32_BaseBoard():
                motherboard_info['manufacturer'] = self._clean_string(board.Manufacturer)
                motherboard_info['product'] = self._clean_string(board.Product)
                motherboard_info['version'] = self._clean_string(board.Version)
                motherboard_info['serial_number'] = self._clean_string(board.SerialNumber)
                break

            # Informations BIOS
            for bios in c.Win32_BIOS():
                motherboard_info['bios_manufacturer'] = self._clean_string(bios.Manufacturer)
                motherboard_info['bios_version'] = self._clean_string(bios.Version)
                motherboard_info['bios_release_date'] = bios.ReleaseDate
                motherboard_info['bios_serial_number'] = self._clean_string(bios.SerialNumber)
                break

        except ImportError:
            self.logger.debug("Module WMI non disponible pour carte mère")
        except Exception as e:
            self.logger.warning(f"Erreur récupération carte mère Windows: {e}")

        return motherboard_info

    def _get_linux_motherboard_info(self) -> Dict[str, Any]:
        """
        Informations carte mère Linux via dmidecode

        Returns:
            dict: Informations carte mère Linux
        """
        motherboard_info = {}

        try:
            # Informations carte mère
            board_info = self._execute_command("dmidecode -t baseboard")
            if board_info:
                motherboard_info.update(self._parse_dmidecode_output(board_info))

            # Informations BIOS
            bios_info = self._execute_command("dmidecode -t bios")
            if bios_info:
                bios_data = self._parse_dmidecode_output(bios_info)
                for key, value in bios_data.items():
                    motherboard_info[f"bios_{key}"] = value

        except Exception as e:
            self.logger.debug(f"Erreur récupération carte mère Linux: {e}")

        return motherboard_info

    def _parse_dmidecode_output(self, output: str) -> Dict[str, Any]:
        """
        Parse la sortie dmidecode

        Args:
            output: Sortie de dmidecode

        Returns:
            dict: Données parsées
        """
        data = {}

        for line in output.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('Handle'):
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()

                if value and value != 'Not Specified':
                    data[key] = self._clean_string(value)

        return data

    def _collect_system_hardware(self) -> Dict[str, Any]:
        """
        Collecte les informations système générales

        Returns:
            dict: Informations système matériel
        """
        system_info = {}

        if sys.platform == "win32":
            try:
                import wmi
                c = wmi.WMI()

                for system in c.Win32_ComputerSystem():
                    system_info['manufacturer'] = self._clean_string(system.Manufacturer)
                    system_info['model'] = self._clean_string(system.Model)
                    system_info['system_type'] = self._clean_string(system.SystemType)
                    system_info['total_physical_memory'] = self._format_bytes(system.TotalPhysicalMemory)
                    break

            except Exception as e:
                self.logger.debug(f"Erreur récupération système Windows: {e}")

        return system_info