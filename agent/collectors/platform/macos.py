"""
Collecteur spécifique macOS pour l'agent d'inventaire

Ce module utilise les outils et API spécifiques macOS :
- sysctl pour les informations système
- system_profiler pour le matériel
- launchctl pour les services
- Commandes Unix spécifiques macOS
"""

import sys
import json
import plistlib
from typing import Dict, Any, List

from ..base import BaseCollector


class MacOSCollector(BaseCollector):
    """
    Collecteur spécifique pour macOS

    Utilise les outils natifs macOS comme sysctl, system_profiler,
    et launchctl pour récupérer des informations détaillées.
    """

    def collect(self) -> Dict[str, Any]:
        """
        Collecte les informations spécifiques macOS

        Returns:
            dict: Informations macOS détaillées
        """
        if sys.platform != "darwin":
            self.logger.warning("MacOSCollector appelé sur une plateforme non-macOS")
            return {}

        self._start_collection()

        macos_info = {
            # Informations système macOS
            'system': self._collect_macos_system_info(),

            # Informations matériel via system_profiler
            'hardware_profiler': self._collect_system_profiler_info(),

            # Services launchd
            'services': self._collect_launchd_services(),

            # Applications installées
            'applications': self._collect_macos_applications(),

            # Préférences système
            'preferences': self._collect_system_preferences(),

            # Utilisateurs et comptes
            'users': self._collect_macos_users(),

            # Configuration réseau avancée
            'network_config': self._collect_network_config(),

            # Informations de sécurité macOS
            'security': self._collect_macos_security(),

            # Environnement et shell
            'environment': self._collect_macos_environment()
        }

        self.last_collection_duration = self._end_collection()
        return macos_info

    def _collect_macos_system_info(self) -> Dict[str, Any]:
        """
        Collecte les informations système macOS via sysctl

        Returns:
            dict: Informations système macOS
        """
        system_info = {}

        # Commandes sysctl importantes pour macOS
        sysctl_commands = {
            # Kernel et système
            'kernel_version': 'kern.version',
            'kernel_boottime': 'kern.boottime',
            'hostname': 'kern.hostname',
            'ostype': 'kern.ostype',
            'osrelease': 'kern.osrelease',
            'osrevision': 'kern.osrevision',

            # Hardware
            'hw_model': 'hw.model',
            'hw_machine': 'hw.machine',
            'hw_ncpu': 'hw.ncpu',
            'hw_physicalcpu': 'hw.physicalcpu',
            'hw_logicalcpu': 'hw.logicalcpu',
            'hw_memsize': 'hw.memsize',
            'hw_pagesize': 'hw.pagesize',

            # CPU spécifique
            'cpu_brand': 'machdep.cpu.brand_string',
            'cpu_vendor': 'machdep.cpu.vendor',
            'cpu_family': 'machdep.cpu.family',
            'cpu_model': 'machdep.cpu.model',
            'cpu_stepping': 'machdep.cpu.stepping',
            'cpu_features': 'machdep.cpu.features',

            # VM et mémoire
            'vm_swapusage': 'vm.swapusage'
        }

        for key, sysctl_key in sysctl_commands.items():
            value = self._execute_command(f"sysctl -n {sysctl_key}")
            if value:
                # Traitement spécial pour certaines valeurs
                if key == 'hw_memsize':
                    try:
                        bytes_value = int(value)
                        system_info[key] = self._format_bytes(bytes_value)
                        system_info[f"{key}_bytes"] = bytes_value
                    except ValueError:
                        system_info[key] = value
                elif key in ['hw_ncpu', 'hw_physicalcpu', 'hw_logicalcpu']:
                    try:
                        system_info[key] = int(value)
                    except ValueError:
                        system_info[key] = value
                else:
                    system_info[key] = self._clean_string(value)

        # Version macOS détaillée
        sw_vers_output = self._execute_command('sw_vers')
        if sw_vers_output:
            for line in sw_vers_output.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    system_info[f"sw_vers_{key}"] = value

        return system_info

    def _collect_system_profiler_info(self) -> Dict[str, Any]:
        """
        Collecte les informations matériel via system_profiler

        Returns:
            dict: Informations system_profiler
        """
        profiler_info = {}

        # Types de données system_profiler importants
        profiler_types = [
            'SPHardwareDataType',      # Informations matériel général
            'SPMemoryDataType',        # Mémoire RAM
            'SPStorageDataType',       # Stockage
            'SPDisplaysDataType',      # Écrans et graphiques
            'SPNetworkDataType',       # Interfaces réseau
            'SPAudioDataType',         # Audio
            'SPUSBDataType',           # Périphériques USB
            'SPSerialATADataType',     # SATA
            'SPThunderboltDataType',   # Thunderbolt
            'SPBluetoothDataType'      # Bluetooth
        ]

        for profiler_type in profiler_types:
            try:
                output = self._execute_command(f'system_profiler {profiler_type} -json')
                if output:
                    try:
                        data = json.loads(output)
                        type_key = profiler_type.lower().replace('sp', '').replace('datatype', '')
                        profiler_info[type_key] = data.get(profiler_type, [])

                    except json.JSONDecodeError as e:
                        self.logger.debug(f"Erreur parsing JSON {profiler_type}: {e}")

            except Exception as e:
                self.logger.debug(f"Erreur system_profiler {profiler_type}: {e}")

        return profiler_info

    def _collect_launchd_services(self) -> Dict[str, Any]:
        """
        Collecte les services launchd

        Returns:
            dict: Informations services launchd
        """
        services_info = {
            'user_services': [],
            'system_services': [],
            'service_counts': {}
        }

        try:
            # Services utilisateur
            user_output = self._execute_command('launchctl list')
            if user_output:
                services_info['user_services'] = self._parse_launchctl_output(user_output)

            # Services système (nécessite sudo, peut ne pas fonctionner)
            try:
                system_output = self._execute_command('sudo launchctl list')
                if system_output:
                    services_info['system_services'] = self._parse_launchctl_output(system_output)
            except Exception:
                # sudo peut ne pas être disponible ou autorisé
                pass

            # Compter les services
            services_info['service_counts'] = {
                'user_services': len(services_info['user_services']),
                'system_services': len(services_info['system_services'])
            }

        except Exception as e:
            self.logger.debug(f"Erreur collecte services launchd: {e}")

        return services_info

    def _parse_launchctl_output(self, output: str) -> List[Dict[str, Any]]:
        """
        Parse la sortie de launchctl list

        Args:
            output: Sortie de launchctl

        Returns:
            list: Services parsés
        """
        services = []

        for line in output.split('\n')[1:]:  # Ignorer l'en-tête
            parts = line.split('\t')
            if len(parts) >= 3:
                service_info = {
                    'pid': parts[0] if parts[0] != '-' else None,
                    'status': parts[1],
                    'label': parts[2]
                }
                services.append(service_info)

        return services[:100]  # Limiter pour éviter trop de données

    def _collect_macos_applications(self) -> Dict[str, Any]:
        """
        Collecte les applications macOS installées

        Returns:
            dict: Applications macOS
        """
        apps_info = {
            'applications': [],
            'application_count': 0
        }

        try:
            # Applications via system_profiler
            output = self._execute_command('system_profiler SPApplicationsDataType -json')
            if output:
                try:
                    data = json.loads(output)
                    apps_data = data.get('SPApplicationsDataType', [])

                    for app in apps_data:
                        app_info = {
                            'name': app.get('_name', ''),
                            'version': app.get('version', ''),
                            'obtained_from': app.get('obtained_from', ''),
                            'last_modified': app.get('lastModified', ''),
                            'path': app.get('path', ''),
                            'kind': app.get('kind', ''),
                            'bundle_id': app.get('info', {}).get('CFBundleIdentifier', '') if isinstance(app.get('info'), dict) else ''
                        }
                        apps_info['applications'].append(app_info)

                    apps_info['application_count'] = len(apps_info['applications'])

                except json.JSONDecodeError as e:
                    self.logger.debug(f"Erreur parsing JSON applications: {e}")

        except Exception as e:
            self.logger.debug(f"Erreur collecte applications macOS: {e}")

        return apps_info

    def _collect_system_preferences(self) -> Dict[str, Any]:
        """
        Collecte les préférences système importantes

        Returns:
            dict: Préférences système
        """
        preferences_info = {}

        # Préférences importantes à collecter
        important_prefs = [
            ('com.apple.dock', 'orientation'),
            ('com.apple.dock', 'autohide'),
            ('com.apple.dock', 'tilesize'),
            ('com.apple.screensaver', 'askForPassword'),
            ('com.apple.screensaver', 'askForPasswordDelay'),
            ('NSGlobalDomain', 'AppleShowAllExtensions'),
            ('NSGlobalDomain', 'NSNavPanelExpandedStateForSaveMode'),
            ('com.apple.finder', 'AppleShowAllFiles'),
            ('com.apple.TimeMachine', 'AutoBackup')
        ]

        for domain, key in important_prefs:
            try:
                value = self._execute_command(f'defaults read {domain} {key} 2>/dev/null')
                if value:
                    pref_key = f"{domain}_{key}".replace('com.apple.', '').replace('NSGlobalDomain_', 'global_')
                    preferences_info[pref_key] = value.strip()

            except Exception as e:
                self.logger.debug(f"Erreur lecture préférence {domain}.{key}: {e}")

        return preferences_info

    def _collect_macos_users(self) -> Dict[str, Any]:
        """
        Collecte les informations utilisateurs macOS

        Returns:
            dict: Informations utilisateurs macOS
        """
        users_info = {
            'local_users': [],
            'current_user': {},
            'login_items': []
        }

        try:
            # Utilisateurs locaux via dscl
            users_output = self._execute_command('dscl . list /Users')
            if users_output:
                user_names = users_output.split('\n')

                for user_name in user_names:
                    if user_name and not user_name.startswith('_'):  # Ignorer les utilisateurs système
                        user_info = {
                            'username': user_name,
                            'real_name': '',
                            'home_directory': '',
                            'shell': '',
                            'uid': ''
                        }

                        # Informations détaillées pour chaque utilisateur
                        user_details = self._execute_command(f'dscl . read /Users/{user_name}')
                        if user_details:
                            for line in user_details.split('\n'):
                                if line.startswith('RealName:'):
                                    user_info['real_name'] = line.split(':', 1)[1].strip()
                                elif line.startswith('NFSHomeDirectory:'):
                                    user_info['home_directory'] = line.split(':', 1)[1].strip()
                                elif line.startswith('UserShell:'):
                                    user_info['shell'] = line.split(':', 1)[1].strip()
                                elif line.startswith('UniqueID:'):
                                    user_info['uid'] = line.split(':', 1)[1].strip()

                        users_info['local_users'].append(user_info)

            # Utilisateur courant
            current_user = self._execute_command('whoami')
            if current_user:
                users_info['current_user']['username'] = current_user.strip()

                # Répertoire home de l'utilisateur courant
                home_dir = self._execute_command('echo $HOME')
                if home_dir:
                    users_info['current_user']['home_directory'] = home_dir.strip()

        except Exception as e:
            self.logger.debug(f"Erreur collecte utilisateurs macOS: {e}")

        return users_info

    def _collect_network_config(self) -> Dict[str, Any]:
        """
        Collecte la configuration réseau avancée macOS

        Returns:
            dict: Configuration réseau macOS
        """
        network_info = {
            'network_services': [],
            'wifi_networks': [],
            'proxy_settings': {}
        }

        try:
            # Services réseau via networksetup
            services_output = self._execute_command('networksetup -listallnetworkservices')
            if services_output:
                services = services_output.split('\n')[1:]  # Ignorer la première ligne
                for service in services:
                    if service and not service.startswith('*'):
                        service_info = {
                            'name': service,
                            'hardware': '',
                            'ip_config': {}
                        }

                        # Hardware pour ce service
                        hardware_output = self._execute_command(f'networksetup -listallhardwareports | grep -A1 "{service}"')
                        if hardware_output:
                            for line in hardware_output.split('\n'):
                                if line.startswith('Hardware Port:'):
                                    service_info['hardware'] = line.split(':', 1)[1].strip()

                        network_info['network_services'].append(service_info)

            # Réseaux WiFi connus
            wifi_output = self._execute_command('networksetup -listpreferredwirelessnetworks en0 2>/dev/null')
            if wifi_output:
                networks = wifi_output.split('\n')[1:]  # Ignorer l'en-tête
                network_info['wifi_networks'] = [net.strip() for net in networks if net.strip()]

        except Exception as e:
            self.logger.debug(f"Erreur collecte réseau macOS: {e}")

        return network_info

    def _collect_macos_security(self) -> Dict[str, Any]:
        """
        Collecte les informations de sécurité macOS

        Returns:
            dict: Informations sécurité macOS
        """
        security_info = {
            'gatekeeper': {},
            'system_integrity': {},
            'firewall': {},
            'keychain_info': {}
        }

        try:
            # Gatekeeper
            gatekeeper_output = self._execute_command('spctl --status')
            if gatekeeper_output:
                security_info['gatekeeper']['status'] = gatekeeper_output.strip()

            # System Integrity Protection (SIP)
            sip_output = self._execute_command('csrutil status')
            if sip_output:
                security_info['system_integrity']['sip_status'] = sip_output.strip()

            # Pare-feu
            firewall_output = self._execute_command('sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null')
            if firewall_output:
                security_info['firewall']['global_state'] = firewall_output.strip()

            # Trousseau par défaut
            keychain_output = self._execute_command('security default-keychain')
            if keychain_output:
                security_info['keychain_info']['default_keychain'] = keychain_output.strip().strip('"')

        except Exception as e:
            self.logger.debug(f"Erreur collecte sécurité macOS: {e}")

        return security_info

    def _collect_macos_environment(self) -> Dict[str, Any]:
        """
        Collecte les variables d'environnement et configuration macOS

        Returns:
            dict: Environnement macOS
        """
        env_info = {
            'shell_info': {},
            'development_tools': {},
            'system_paths': {}
        }

        try:
            # Informations shell
            shell_output = self._execute_command('echo $SHELL')
            if shell_output:
                env_info['shell_info']['current_shell'] = shell_output.strip()

            shell_version = self._execute_command('echo $0')
            if shell_version:
                env_info['shell_info']['shell_version'] = shell_version.strip()

            # Outils de développement
            xcode_output = self._execute_command('xcodebuild -version 2>/dev/null')
            if xcode_output:
                env_info['development_tools']['xcode'] = xcode_output.split('\n')[0] if xcode_output else ''

            # Command Line Tools
            clt_output = self._execute_command('pkgutil --pkg-info=com.apple.pkg.CLTools_Executables 2>/dev/null')
            if clt_output:
                for line in clt_output.split('\n'):
                    if line.startswith('version:'):
                        env_info['development_tools']['command_line_tools'] = line.split(':', 1)[1].strip()

            # Homebrew
            brew_output = self._execute_command('brew --version 2>/dev/null')
            if brew_output:
                env_info['development_tools']['homebrew'] = brew_output.split('\n')[0] if brew_output else ''

            # Chemins système importants
            path_vars = ['PATH', 'MANPATH', 'INFOPATH']
            for var in path_vars:
                value = self._execute_command(f'echo ${var}')
                if value:
                    # Tronquer si trop long
                    if len(value) > 300:
                        value = value[:300] + "..."
                    env_info['system_paths'][var.lower()] = value.strip()

        except Exception as e:
            self.logger.debug(f"Erreur collecte environnement macOS: {e}")

        return env_info