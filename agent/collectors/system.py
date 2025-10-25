"""
Collecteur d'informations système pour l'agent d'inventaire

Ce module collecte les informations système générales :
- Informations CPU
- Mémoire
- Stockage
- Temps de fonctionnement
- Charge système
"""

import os
import sys
import platform
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any

from .base import BaseCollector


class SystemCollector(BaseCollector):
    """
    Collecteur d'informations système générales

    Utilise principalement la bibliothèque psutil pour récupérer
    les informations système multi-plateforme.
    """

    def collect(self) -> Dict[str, Any]:
        """
        Collecte toutes les informations système

        Returns:
            dict: Informations système complètes
        """
        self._start_collection()

        system_info = {
            # Informations CPU
            'cpu': self._collect_cpu_info(),

            # Informations mémoire
            'memory': self._collect_memory_info(),

            # Informations stockage
            'storage': self._collect_storage_info(),

            # Informations système
            'uptime': self._collect_uptime_info(),
            'load_average': self._collect_load_average(),
            'processes_count': self._collect_process_count(),

            # Informations utilisateur
            'users': self._collect_users_info(),

            # Informations environnement
            'environment': self._collect_environment_info()
        }

        self.last_collection_duration = self._end_collection()
        return system_info

    def _collect_cpu_info(self) -> Dict[str, Any]:
        """
        Collecte les informations CPU

        Returns:
            dict: Informations détaillées du processeur
        """
        cpu_info = {}

        # Informations de base
        cpu_info['physical_cores'] = self._safe_execute(
            lambda: psutil.cpu_count(logical=False),
            "Erreur récupération cores physiques",
            0
        )

        cpu_info['logical_cores'] = self._safe_execute(
            lambda: psutil.cpu_count(logical=True),
            "Erreur récupération cores logiques",
            0
        )

        # Fréquences CPU
        cpu_freq = self._safe_execute(
            lambda: psutil.cpu_freq(),
            "Erreur récupération fréquence CPU"
        )

        if cpu_freq:
            cpu_info['frequency_current'] = self._format_frequency(cpu_freq.current * 1_000_000)
            cpu_info['frequency_min'] = self._format_frequency(cpu_freq.min * 1_000_000)
            cpu_info['frequency_max'] = self._format_frequency(cpu_freq.max * 1_000_000)
        else:
            cpu_info['frequency_current'] = "N/A"
            cpu_info['frequency_min'] = "N/A"
            cpu_info['frequency_max'] = "N/A"

        # Utilisation CPU (moyenne sur 1 seconde)
        cpu_info['usage_percent'] = self._safe_execute(
            lambda: round(psutil.cpu_percent(interval=1), 1),
            "Erreur récupération utilisation CPU",
            0.0
        )

        # Utilisation CPU par core
        cpu_info['usage_per_core'] = self._safe_execute(
            lambda: [round(x, 1) for x in psutil.cpu_percent(interval=1, percpu=True)],
            "Erreur récupération utilisation par core",
            []
        )

        # Nom du processeur (spécifique à la plateforme)
        cpu_info['model'] = self._get_cpu_model()

        # Architecture
        cpu_info['architecture'] = platform.machine()

        return cpu_info

    def _get_cpu_model(self) -> str:
        """
        Récupère le nom/modèle du processeur selon la plateforme

        Returns:
            str: Nom du processeur
        """
        if sys.platform == "win32":
            # Windows - utiliser wmi ou registre
            try:
                import wmi
                c = wmi.WMI()
                for processor in c.Win32_Processor():
                    return self._clean_string(processor.Name)
            except ImportError:
                pass

            # Fallback: essayer le registre Windows
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                   r"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0")
                cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                winreg.CloseKey(key)
                return self._clean_string(cpu_name)
            except Exception:
                pass

        elif sys.platform == "darwin":
            # macOS - utiliser sysctl
            cpu_name = self._execute_command("sysctl -n machdep.cpu.brand_string")
            if cpu_name:
                return self._clean_string(cpu_name)

        else:
            # Linux - lire /proc/cpuinfo
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            cpu_name = line.split(':', 1)[1].strip()
                            return self._clean_string(cpu_name)
            except Exception:
                pass

        # Fallback
        return platform.processor() or "Unknown"

    def _collect_memory_info(self) -> Dict[str, Any]:
        """
        Collecte les informations mémoire

        Returns:
            dict: Informations mémoire système
        """
        memory_info = {}

        # Mémoire virtuelle (RAM)
        virtual_mem = self._safe_execute(
            lambda: psutil.virtual_memory(),
            "Erreur récupération mémoire virtuelle"
        )

        if virtual_mem:
            memory_info['total'] = self._format_bytes(virtual_mem.total)
            memory_info['available'] = self._format_bytes(virtual_mem.available)
            memory_info['used'] = self._format_bytes(virtual_mem.used)
            memory_info['usage_percent'] = round(virtual_mem.percent, 1)
            memory_info['free'] = self._format_bytes(virtual_mem.free)

        # Mémoire swap
        swap_mem = self._safe_execute(
            lambda: psutil.swap_memory(),
            "Erreur récupération mémoire swap"
        )

        if swap_mem:
            memory_info['swap_total'] = self._format_bytes(swap_mem.total)
            memory_info['swap_used'] = self._format_bytes(swap_mem.used)
            memory_info['swap_free'] = self._format_bytes(swap_mem.free)
            memory_info['swap_usage_percent'] = round(swap_mem.percent, 1)

        return memory_info

    def _collect_storage_info(self) -> Dict[str, Any]:
        """
        Collecte les informations de stockage

        Returns:
            dict: Informations des disques et partitions
        """
        storage_info = {
            'partitions': [],
            'total_storage': 0,
            'used_storage': 0,
            'free_storage': 0
        }

        # Récupérer toutes les partitions
        partitions = self._safe_execute(
            lambda: psutil.disk_partitions(),
            "Erreur récupération partitions",
            []
        )

        total_size = 0
        total_used = 0
        total_free = 0

        for partition in partitions:
            try:
                # Informations de la partition
                partition_info = {
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'filesystem': partition.fstype
                }

                # Utilisation de la partition
                try:
                    disk_usage = psutil.disk_usage(partition.mountpoint)
                    partition_info['total'] = self._format_bytes(disk_usage.total)
                    partition_info['used'] = self._format_bytes(disk_usage.used)
                    partition_info['free'] = self._format_bytes(disk_usage.free)
                    partition_info['usage_percent'] = round(
                        (disk_usage.used / disk_usage.total) * 100, 1
                    ) if disk_usage.total > 0 else 0

                    # Additionner pour le total
                    total_size += disk_usage.total
                    total_used += disk_usage.used
                    total_free += disk_usage.free

                except PermissionError:
                    # Partition non accessible
                    partition_info['total'] = "N/A"
                    partition_info['used'] = "N/A"
                    partition_info['free'] = "N/A"
                    partition_info['usage_percent'] = "N/A"

                storage_info['partitions'].append(partition_info)

            except Exception as e:
                self.logger.warning(f"Erreur traitement partition {partition.device}: {e}")

        # Totaux
        storage_info['total_storage'] = self._format_bytes(total_size)
        storage_info['used_storage'] = self._format_bytes(total_used)
        storage_info['free_storage'] = self._format_bytes(total_free)

        return storage_info

    def _collect_uptime_info(self) -> Dict[str, Any]:
        """
        Collecte les informations de temps de fonctionnement

        Returns:
            dict: Informations uptime
        """
        uptime_info = {}

        # Temps de démarrage du système
        boot_time = self._safe_execute(
            lambda: psutil.boot_time(),
            "Erreur récupération temps de démarrage"
        )

        if boot_time:
            boot_datetime = datetime.fromtimestamp(boot_time)
            uptime_duration = datetime.now() - boot_datetime

            uptime_info['boot_time'] = boot_datetime.isoformat()
            uptime_info['uptime_seconds'] = int(uptime_duration.total_seconds())
            uptime_info['uptime_human'] = self._format_uptime(uptime_duration)

        return uptime_info

    def _format_uptime(self, uptime_duration: timedelta) -> str:
        """
        Formate la durée d'uptime en format lisible

        Args:
            uptime_duration: Durée d'uptime

        Returns:
            str: Uptime formaté (ex: "5 jours, 3 heures, 22 minutes")
        """
        days = uptime_duration.days
        hours, remainder = divmod(uptime_duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days} jour{'s' if days > 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} heure{'s' if hours > 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")

        if not parts:
            return "Moins d'une minute"

        return ", ".join(parts)

    def _collect_load_average(self) -> Dict[str, Any]:
        """
        Collecte les informations de charge système

        Returns:
            dict: Charge système (Linux/macOS principalement)
        """
        load_info = {}

        # Charge moyenne (Unix seulement)
        if hasattr(os, 'getloadavg'):
            try:
                load1, load5, load15 = os.getloadavg()
                load_info['load_1min'] = round(load1, 2)
                load_info['load_5min'] = round(load5, 2)
                load_info['load_15min'] = round(load15, 2)
            except Exception as e:
                self.logger.warning(f"Erreur récupération charge système: {e}")

        return load_info

    def _collect_process_count(self) -> int:
        """
        Compte le nombre de processus en cours

        Returns:
            int: Nombre de processus
        """
        return self._safe_execute(
            lambda: len(psutil.pids()),
            "Erreur récupération nombre de processus",
            0
        )

    def _collect_users_info(self) -> Dict[str, Any]:
        """
        Collecte les informations utilisateurs

        Returns:
            dict: Informations utilisateurs connectés
        """
        users_info = {
            'logged_users': [],
            'user_count': 0
        }

        # Utilisateurs connectés
        users = self._safe_execute(
            lambda: psutil.users(),
            "Erreur récupération utilisateurs",
            []
        )

        for user in users:
            user_info = {
                'name': user.name,
                'terminal': user.terminal,
                'host': user.host,
                'started': datetime.fromtimestamp(user.started).isoformat()
            }
            users_info['logged_users'].append(user_info)

        users_info['user_count'] = len(users_info['logged_users'])

        return users_info

    def _collect_environment_info(self) -> Dict[str, Any]:
        """
        Collecte les informations d'environnement système

        Returns:
            dict: Variables d'environnement importantes
        """
        env_info = {}

        # Variables importantes à collecter
        important_vars = [
            'PATH', 'HOME', 'USER', 'USERNAME', 'USERPROFILE',
            'COMPUTERNAME', 'HOSTNAME', 'LANG', 'TZ'
        ]

        for var in important_vars:
            value = os.environ.get(var)
            if value:
                # Tronquer PATH s'il est trop long
                if var == 'PATH' and len(value) > 200:
                    value = value[:200] + "..."
                env_info[var.lower()] = value

        # Répertoire de travail actuel
        env_info['current_directory'] = os.getcwd()

        # Répertoire temporaire
        env_info['temp_directory'] = self._safe_execute(
            lambda: os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp',
            "Erreur récupération répertoire temporaire",
            "N/A"
        )

        return env_info