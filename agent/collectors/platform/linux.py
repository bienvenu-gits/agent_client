"""
Collecteur spécifique Linux pour l'agent d'inventaire

Ce module utilise les interfaces Linux spécifiques :
- Système de fichiers /proc et /sys
- Commandes Unix standard
- Gestionnaires de paquets
- Services systemd
"""

import os
import sys
import re
from typing import Dict, Any, List

from ..base import BaseCollector


class LinuxCollector(BaseCollector):
    """
    Collecteur spécifique pour Linux

    Utilise les interfaces spécifiques Linux comme /proc, /sys,
    et les commandes Unix pour récupérer des informations détaillées.
    """

    def collect(self) -> Dict[str, Any]:
        """
        Collecte les informations spécifiques Linux

        Returns:
            dict: Informations Linux détaillées
        """
        if not sys.platform.startswith('linux'):
            self.logger.warning("LinuxCollector appelé sur une plateforme non-Linux")
            return {}

        self._start_collection()

        linux_info = {
            # Distribution et version
            'distribution': self._collect_distribution_info(),

            # Kernel et modules
            'kernel': self._collect_kernel_info(),

            # Services systemd
            'services': self._collect_systemd_services(),

            # Montages et filesystems
            'filesystems': self._collect_filesystem_info(),

            # Processus système
            'processes': self._collect_process_info(),

            # Configuration réseau avancée
            'network_advanced': self._collect_network_advanced(),

            # Informations matériel depuis /sys
            'hardware_sys': self._collect_sys_hardware(),

            # Utilisateurs et groupes
            'users_groups': self._collect_users_groups(),

            # Cron jobs et tâches planifiées
            'scheduled_tasks': self._collect_scheduled_tasks(),

            # Variables d'environnement système
            'environment': self._collect_linux_environment()
        }

        self.last_collection_duration = self._end_collection()
        return linux_info

    def _collect_distribution_info(self) -> Dict[str, Any]:
        """
        Collecte les informations de distribution Linux

        Returns:
            dict: Informations distribution
        """
        distro_info = {}

        # Méthode 1: /etc/os-release (standard)
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        value = value.strip('"')
                        distro_info[key.lower()] = value

        except FileNotFoundError:
            self.logger.debug("/etc/os-release non trouvé")
        except Exception as e:
            self.logger.warning(f"Erreur lecture /etc/os-release: {e}")

        # Méthode 2: /etc/lsb-release (Ubuntu/Debian)
        try:
            with open('/etc/lsb-release', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        value = value.strip('"')
                        distro_info[f"lsb_{key.lower()}"] = value

        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.debug(f"Erreur lecture /etc/lsb-release: {e}")

        # Méthode 3: Fichiers spécifiques aux distributions
        distro_files = {
            '/etc/redhat-release': 'redhat_release',
            '/etc/debian_version': 'debian_version',
            '/etc/suse-release': 'suse_release',
            '/etc/arch-release': 'arch_release'
        }

        for file_path, key in distro_files.items():
            content = self._read_file(file_path)
            if content:
                distro_info[key] = content

        return distro_info

    def _collect_kernel_info(self) -> Dict[str, Any]:
        """
        Collecte les informations kernel Linux

        Returns:
            dict: Informations kernel
        """
        kernel_info = {}

        # Version kernel depuis /proc/version
        version_content = self._read_file('/proc/version')
        if version_content:
            kernel_info['version_full'] = version_content

        # Informations depuis uname
        uname_info = self._execute_command('uname -a')
        if uname_info:
            kernel_info['uname'] = uname_info

        # Version kernel
        kernel_version = self._execute_command('uname -r')
        if kernel_version:
            kernel_info['version'] = kernel_version

        # Architecture
        arch = self._execute_command('uname -m')
        if arch:
            kernel_info['architecture'] = arch

        # Modules chargés
        try:
            with open('/proc/modules', 'r') as f:
                modules = []
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        module_info = {
                            'name': parts[0],
                            'size': parts[1],
                            'used_by': parts[3] if len(parts) > 3 else ''
                        }
                        modules.append(module_info)

                kernel_info['loaded_modules'] = modules[:50]  # Limiter pour éviter trop de données
                kernel_info['loaded_modules_count'] = len(modules)

        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.debug(f"Erreur lecture /proc/modules: {e}")

        # Paramètres kernel depuis /proc/sys
        kernel_params = {}
        important_params = [
            '/proc/sys/kernel/hostname',
            '/proc/sys/kernel/ostype',
            '/proc/sys/kernel/osrelease',
            '/proc/sys/kernel/version'
        ]

        for param_file in important_params:
            param_name = os.path.basename(param_file)
            param_value = self._read_file(param_file)
            if param_value:
                kernel_params[param_name] = param_value

        kernel_info['parameters'] = kernel_params

        return kernel_info

    def _collect_systemd_services(self) -> Dict[str, Any]:
        """
        Collecte les services systemd

        Returns:
            dict: Informations services systemd
        """
        services_info = {
            'enabled_services': [],
            'active_services': [],
            'failed_services': [],
            'service_counts': {}
        }

        try:
            # Services actifs
            active_output = self._execute_command('systemctl list-units --type=service --state=active --no-pager')
            if active_output:
                services_info['active_services'] = self._parse_systemctl_output(active_output)

            # Services en échec
            failed_output = self._execute_command('systemctl list-units --type=service --state=failed --no-pager')
            if failed_output:
                services_info['failed_services'] = self._parse_systemctl_output(failed_output)

            # Services activés au démarrage
            enabled_output = self._execute_command('systemctl list-unit-files --type=service --state=enabled --no-pager')
            if enabled_output:
                services_info['enabled_services'] = self._parse_systemctl_output(enabled_output)

            # Statistiques
            services_info['service_counts'] = {
                'active': len(services_info['active_services']),
                'failed': len(services_info['failed_services']),
                'enabled': len(services_info['enabled_services'])
            }

        except Exception as e:
            self.logger.debug(f"Erreur collecte services systemd: {e}")

        return services_info

    def _parse_systemctl_output(self, output: str) -> List[Dict[str, Any]]:
        """
        Parse la sortie des commandes systemctl

        Args:
            output: Sortie de systemctl

        Returns:
            list: Services parsés
        """
        services = []

        for line in output.split('\n')[1:]:  # Ignorer l'en-tête
            line = line.strip()
            if line and not line.startswith('●') and '.service' in line:
                parts = line.split()
                if len(parts) >= 4:
                    service_info = {
                        'name': parts[0],
                        'load_state': parts[1] if len(parts) > 1 else '',
                        'active_state': parts[2] if len(parts) > 2 else '',
                        'sub_state': parts[3] if len(parts) > 3 else '',
                        'description': ' '.join(parts[4:]) if len(parts) > 4 else ''
                    }
                    services.append(service_info)

        return services[:50]  # Limiter pour éviter trop de données

    def _collect_filesystem_info(self) -> Dict[str, Any]:
        """
        Collecte les informations de filesystems

        Returns:
            dict: Informations filesystems
        """
        fs_info = {
            'mounts': [],
            'supported_filesystems': [],
            'filesystem_stats': {}
        }

        # Montages actuels depuis /proc/mounts
        try:
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 6:
                        mount_info = {
                            'device': parts[0],
                            'mountpoint': parts[1],
                            'filesystem': parts[2],
                            'options': parts[3].split(','),
                            'dump': parts[4],
                            'pass': parts[5]
                        }
                        fs_info['mounts'].append(mount_info)

        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.debug(f"Erreur lecture /proc/mounts: {e}")

        # Filesystems supportés depuis /proc/filesystems
        try:
            with open('/proc/filesystems', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('nodev'):
                        fs_info['supported_filesystems'].append(line)

        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.debug(f"Erreur lecture /proc/filesystems: {e}")

        return fs_info

    def _collect_process_info(self) -> Dict[str, Any]:
        """
        Collecte les informations processus avancées

        Returns:
            dict: Informations processus
        """
        process_info = {
            'process_count': 0,
            'top_cpu_processes': [],
            'top_memory_processes': [],
            'process_stats': {}
        }

        try:
            # Statistiques depuis /proc/stat
            stat_content = self._read_file('/proc/stat')
            if stat_content:
                for line in stat_content.split('\n'):
                    if line.startswith('processes'):
                        process_info['total_processes_created'] = int(line.split()[1])
                    elif line.startswith('procs_running'):
                        process_info['running_processes'] = int(line.split()[1])
                    elif line.startswith('procs_blocked'):
                        process_info['blocked_processes'] = int(line.split()[1])

            # Top processus par CPU (via ps)
            ps_cpu_output = self._execute_command('ps -eo pid,ppid,cmd,pcpu,pmem --sort=-pcpu --no-headers | head -10')
            if ps_cpu_output:
                for line in ps_cpu_output.split('\n'):
                    if line.strip():
                        parts = line.split(None, 4)
                        if len(parts) >= 5:
                            proc_info = {
                                'pid': parts[0],
                                'ppid': parts[1],
                                'cpu_percent': parts[3],
                                'mem_percent': parts[4],
                                'command': parts[4][:100] if len(parts[4]) > 100 else parts[4]
                            }
                            process_info['top_cpu_processes'].append(proc_info)

        except Exception as e:
            self.logger.debug(f"Erreur collecte processus: {e}")

        return process_info

    def _collect_network_advanced(self) -> Dict[str, Any]:
        """
        Collecte les informations réseau avancées Linux

        Returns:
            dict: Informations réseau avancées
        """
        network_info = {
            'iptables_rules': [],
            'network_namespaces': [],
            'tcp_connections': {},
            'network_statistics': {}
        }

        try:
            # Statistiques réseau depuis /proc/net/dev
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]  # Ignorer les 2 premières lignes
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 17:
                        interface = parts[0].rstrip(':')
                        network_info['network_statistics'][interface] = {
                            'rx_bytes': int(parts[1]),
                            'rx_packets': int(parts[2]),
                            'rx_errors': int(parts[3]),
                            'tx_bytes': int(parts[9]),
                            'tx_packets': int(parts[10]),
                            'tx_errors': int(parts[11])
                        }

        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.debug(f"Erreur lecture /proc/net/dev: {e}")

        # Namespaces réseau
        try:
            ns_output = self._execute_command('ip netns list')
            if ns_output:
                network_info['network_namespaces'] = ns_output.split('\n')

        except Exception as e:
            self.logger.debug(f"Erreur récupération namespaces: {e}")

        return network_info

    def _collect_sys_hardware(self) -> Dict[str, Any]:
        """
        Collecte les informations matériel depuis /sys

        Returns:
            dict: Informations matériel /sys
        """
        hardware_info = {
            'dmi_info': {},
            'thermal_zones': [],
            'power_supply': []
        }

        # Informations DMI (Desktop Management Interface)
        dmi_base = '/sys/class/dmi/id'
        dmi_files = [
            'bios_vendor', 'bios_version', 'bios_date',
            'board_name', 'board_vendor', 'board_version',
            'chassis_type', 'chassis_vendor',
            'product_name', 'product_version', 'product_serial',
            'sys_vendor'
        ]

        for dmi_file in dmi_files:
            dmi_path = os.path.join(dmi_base, dmi_file)
            dmi_value = self._read_file(dmi_path)
            if dmi_value:
                hardware_info['dmi_info'][dmi_file] = self._clean_string(dmi_value)

        # Zones thermiques
        try:
            thermal_base = '/sys/class/thermal'
            if os.path.exists(thermal_base):
                for item in os.listdir(thermal_base):
                    if item.startswith('thermal_zone'):
                        zone_path = os.path.join(thermal_base, item)
                        temp_file = os.path.join(zone_path, 'temp')
                        type_file = os.path.join(zone_path, 'type')

                        temp = self._read_file(temp_file)
                        zone_type = self._read_file(type_file)

                        if temp:
                            thermal_info = {
                                'zone': item,
                                'type': zone_type or 'unknown',
                                'temperature_raw': temp,
                                'temperature_celsius': int(temp) / 1000 if temp.isdigit() else None
                            }
                            hardware_info['thermal_zones'].append(thermal_info)

        except Exception as e:
            self.logger.debug(f"Erreur collecte zones thermiques: {e}")

        # Alimentations
        try:
            power_base = '/sys/class/power_supply'
            if os.path.exists(power_base):
                for item in os.listdir(power_base):
                    power_path = os.path.join(power_base, item)
                    type_file = os.path.join(power_path, 'type')
                    status_file = os.path.join(power_path, 'status')

                    power_type = self._read_file(type_file)
                    power_status = self._read_file(status_file)

                    power_info = {
                        'name': item,
                        'type': power_type,
                        'status': power_status
                    }
                    hardware_info['power_supply'].append(power_info)

        except Exception as e:
            self.logger.debug(f"Erreur collecte alimentations: {e}")

        return hardware_info

    def _collect_users_groups(self) -> Dict[str, Any]:
        """
        Collecte les utilisateurs et groupes Linux

        Returns:
            dict: Informations utilisateurs et groupes
        """
        users_groups_info = {
            'users': [],
            'groups': [],
            'user_count': 0,
            'group_count': 0
        }

        # Utilisateurs depuis /etc/passwd
        try:
            with open('/etc/passwd', 'r') as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) >= 7:
                        user_info = {
                            'username': parts[0],
                            'uid': parts[2],
                            'gid': parts[3],
                            'gecos': parts[4],
                            'home': parts[5],
                            'shell': parts[6]
                        }
                        users_groups_info['users'].append(user_info)

                users_groups_info['user_count'] = len(users_groups_info['users'])

        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.debug(f"Erreur lecture /etc/passwd: {e}")

        # Groupes depuis /etc/group
        try:
            with open('/etc/group', 'r') as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) >= 4:
                        group_info = {
                            'groupname': parts[0],
                            'gid': parts[2],
                            'members': parts[3].split(',') if parts[3] else []
                        }
                        users_groups_info['groups'].append(group_info)

                users_groups_info['group_count'] = len(users_groups_info['groups'])

        except FileNotFoundError:
            pass
        except Exception as e:
            self.logger.debug(f"Erreur lecture /etc/group: {e}")

        return users_groups_info

    def _collect_scheduled_tasks(self) -> Dict[str, Any]:
        """
        Collecte les tâches planifiées (cron)

        Returns:
            dict: Informations tâches planifiées
        """
        tasks_info = {
            'system_crontab': [],
            'user_crontabs': {},
            'anacron_jobs': []
        }

        # Crontab système
        system_crontab = self._read_file('/etc/crontab')
        if system_crontab:
            tasks_info['system_crontab'] = system_crontab.split('\n')

        # Répertoires cron.d
        cron_dirs = ['/etc/cron.d', '/etc/cron.daily', '/etc/cron.weekly', '/etc/cron.monthly']

        for cron_dir in cron_dirs:
            try:
                if os.path.exists(cron_dir):
                    tasks_info[os.path.basename(cron_dir)] = os.listdir(cron_dir)
            except Exception as e:
                self.logger.debug(f"Erreur lecture {cron_dir}: {e}")

        # Anacron
        anacrontab = self._read_file('/etc/anacrontab')
        if anacrontab:
            tasks_info['anacron_jobs'] = anacrontab.split('\n')

        return tasks_info

    def _collect_linux_environment(self) -> Dict[str, Any]:
        """
        Collecte les variables d'environnement Linux

        Returns:
            dict: Variables d'environnement Linux
        """
        env_info = {
            'init_system': self._detect_init_system(),
            'runlevel': self._get_runlevel(),
            'selinux_status': self._get_selinux_status(),
            'apparmor_status': self._get_apparmor_status()
        }

        return env_info

    def _detect_init_system(self) -> str:
        """Détecte le système d'init utilisé"""
        if os.path.exists('/run/systemd/system'):
            return 'systemd'
        elif os.path.exists('/sbin/upstart'):
            return 'upstart'
        elif os.path.exists('/sbin/init'):
            return 'sysv'
        else:
            return 'unknown'

    def _get_runlevel(self) -> str:
        """Récupère le runlevel actuel"""
        runlevel = self._execute_command('runlevel')
        if runlevel:
            return runlevel.split()[-1] if runlevel.split() else 'unknown'
        return 'unknown'

    def _get_selinux_status(self) -> str:
        """Récupère le statut SELinux"""
        status = self._execute_command('sestatus 2>/dev/null | grep "SELinux status"')
        if status:
            return status.split(':')[-1].strip()
        return 'unknown'

    def _get_apparmor_status(self) -> str:
        """Récupère le statut AppArmor"""
        if os.path.exists('/sys/module/apparmor'):
            status = self._execute_command('aa-status 2>/dev/null | head -1')
            if status:
                return status.strip()
        return 'not_installed'