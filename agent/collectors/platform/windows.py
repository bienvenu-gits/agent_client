"""
Collecteur spécifique Windows pour l'agent d'inventaire

Ce module utilise les API Windows spécifiques :
- WMI (Windows Management Instrumentation)
- Registre Windows
- PowerShell
- API Win32
"""

import sys
import json
from typing import Dict, Any

from ..base import BaseCollector


class WindowsCollector(BaseCollector):
    """
    Collecteur spécifique pour Windows

    Utilise WMI, le registre Windows et PowerShell pour récupérer
    des informations détaillées spécifiques à Windows.
    """

    def collect(self) -> Dict[str, Any]:
        """
        Collecte les informations spécifiques Windows

        Returns:
            dict: Informations Windows détaillées
        """
        if sys.platform != "win32":
            self.logger.warning("WindowsCollector appelé sur une plateforme non-Windows")
            return {}

        self._start_collection()

        windows_info = {
            # Informations système Windows
            'system': self._collect_windows_system_info(),

            # Services Windows
            'services': self._collect_windows_services(),

            # Informations domaine/workgroup
            'domain_info': self._collect_domain_info(),

            # Fonctionnalités Windows installées
            'features': self._collect_windows_features(),

            # Informations de sécurité
            'security': self._collect_security_info(),

            # Informations utilisateurs locaux
            'users': self._collect_local_users(),

            # Variables d'environnement spécifiques
            'environment': self._collect_windows_environment(),

            # Informations de démarrage
            'boot_info': self._collect_boot_info()
        }

        self.last_collection_duration = self._end_collection()
        return windows_info

    def _collect_windows_system_info(self) -> Dict[str, Any]:
        """
        Collecte les informations système Windows via WMI

        Returns:
            dict: Informations système Windows
        """
        system_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Informations système général
            for system in c.Win32_ComputerSystem():
                system_info['domain'] = self._clean_string(system.Domain)
                system_info['workgroup'] = self._clean_string(system.Workgroup)
                system_info['part_of_domain'] = system.PartOfDomain
                system_info['roles'] = list(system.Roles) if system.Roles else []
                system_info['system_type'] = self._clean_string(system.SystemType)
                system_info['manufacturer'] = self._clean_string(system.Manufacturer)
                system_info['model'] = self._clean_string(system.Model)
                system_info['total_physical_memory'] = system.TotalPhysicalMemory
                break

            # Informations version Windows
            for os_info in c.Win32_OperatingSystem():
                system_info['windows_version'] = self._clean_string(os_info.Version)
                system_info['windows_build'] = self._clean_string(os_info.BuildNumber)
                system_info['windows_caption'] = self._clean_string(os_info.Caption)
                system_info['windows_architecture'] = self._clean_string(os_info.OSArchitecture)
                system_info['install_date'] = os_info.InstallDate
                system_info['last_boot_time'] = os_info.LastBootUpTime
                system_info['system_directory'] = self._clean_string(os_info.SystemDirectory)
                system_info['windows_directory'] = self._clean_string(os_info.WindowsDirectory)
                system_info['registered_user'] = self._clean_string(os_info.RegisteredUser)
                system_info['organization'] = self._clean_string(os_info.Organization)
                system_info['serial_number'] = self._clean_string(os_info.SerialNumber)
                break

            # Informations processeur spécifiques Windows
            for processor in c.Win32_Processor():
                system_info['processor_id'] = self._clean_string(processor.ProcessorId)
                system_info['processor_revision'] = processor.Revision
                break

        except ImportError:
            self.logger.warning("Module WMI non disponible")
        except Exception as e:
            self.logger.error(f"Erreur collecte système Windows: {e}")

        return system_info

    def _collect_windows_services(self) -> Dict[str, Any]:
        """
        Collecte les services Windows

        Returns:
            dict: Informations sur les services Windows
        """
        services_info = {
            'total_services': 0,
            'running_services': 0,
            'stopped_services': 0,
            'services': []
        }

        try:
            import wmi
            c = wmi.WMI()

            all_services = list(c.Win32_Service())
            services_info['total_services'] = len(all_services)

            for service in all_services:
                service_info = {
                    'name': self._clean_string(service.Name),
                    'display_name': self._clean_string(service.DisplayName),
                    'state': self._clean_string(service.State),
                    'start_mode': self._clean_string(service.StartMode),
                    'service_type': self._clean_string(service.ServiceType),
                    'description': self._clean_string(service.Description)
                }

                # Compter les services par état
                if service.State == 'Running':
                    services_info['running_services'] += 1
                elif service.State == 'Stopped':
                    services_info['stopped_services'] += 1

                services_info['services'].append(service_info)

            # Limiter la liste pour éviter trop de données
            services_info['services'] = services_info['services'][:100]

        except ImportError:
            self.logger.warning("Module WMI non disponible pour services")
        except Exception as e:
            self.logger.error(f"Erreur collecte services Windows: {e}")

        return services_info

    def _collect_domain_info(self) -> Dict[str, Any]:
        """
        Collecte les informations domaine/workgroup

        Returns:
            dict: Informations domaine
        """
        domain_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Informations domaine depuis ComputerSystem
            for system in c.Win32_ComputerSystem():
                domain_info['current_domain'] = self._clean_string(system.Domain)
                domain_info['part_of_domain'] = system.PartOfDomain
                domain_info['workgroup'] = self._clean_string(system.Workgroup)
                break

            # Informations contrôleur de domaine
            try:
                for dc in c.Win32_NTDomain():
                    domain_info['domain_controller_name'] = self._clean_string(dc.DomainControllerName)
                    domain_info['domain_controller_address'] = self._clean_string(dc.DomainControllerAddress)
                    break
            except Exception:
                # Pas de contrôleur de domaine (machine workgroup)
                pass

        except ImportError:
            self.logger.warning("Module WMI non disponible pour domaine")
        except Exception as e:
            self.logger.error(f"Erreur collecte domaine: {e}")

        return domain_info

    def _collect_windows_features(self) -> Dict[str, Any]:
        """
        Collecte les fonctionnalités Windows installées

        Returns:
            dict: Fonctionnalités Windows
        """
        features_info = {
            'installed_features': [],
            'total_features': 0
        }

        try:
            # Utiliser PowerShell pour récupérer les fonctionnalités
            ps_command = "Get-WindowsFeature | Where-Object {$_.InstallState -eq 'Installed'} | Select-Object Name, DisplayName | ConvertTo-Json"

            output = self._execute_command(f'powershell -Command "{ps_command}"')
            if output:
                try:
                    features_data = json.loads(output)

                    # Gérer le cas d'un seul élément
                    if isinstance(features_data, dict):
                        features_data = [features_data]

                    for feature in features_data:
                        feature_info = {
                            'name': feature.get('Name', ''),
                            'display_name': feature.get('DisplayName', '')
                        }
                        features_info['installed_features'].append(feature_info)

                    features_info['total_features'] = len(features_info['installed_features'])

                except json.JSONDecodeError:
                    self.logger.debug("Erreur parsing JSON fonctionnalités Windows")

        except Exception as e:
            self.logger.debug(f"Erreur collecte fonctionnalités Windows: {e}")

        return features_info

    def _collect_security_info(self) -> Dict[str, Any]:
        """
        Collecte les informations de sécurité Windows

        Returns:
            dict: Informations sécurité
        """
        security_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Antivirus installés
            security_info['antivirus'] = []
            try:
                for av in c.Win32_VirusCheckResult():
                    av_info = {
                        'name': self._clean_string(av.DisplayName),
                        'instance_guid': self._clean_string(av.InstanceGuid),
                        'path_to_signature_file': self._clean_string(av.PathToSignedProductExe)
                    }
                    security_info['antivirus'].append(av_info)
            except Exception:
                # Win32_VirusCheckResult peut ne pas être disponible
                pass

            # Pare-feu Windows
            try:
                ps_command = "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json"
                output = self._execute_command(f'powershell -Command "{ps_command}"')
                if output:
                    firewall_data = json.loads(output)
                    if isinstance(firewall_data, dict):
                        firewall_data = [firewall_data]
                    security_info['firewall_profiles'] = firewall_data
            except Exception:
                pass

        except ImportError:
            self.logger.warning("Module WMI non disponible pour sécurité")
        except Exception as e:
            self.logger.error(f"Erreur collecte sécurité Windows: {e}")

        return security_info

    def _collect_local_users(self) -> Dict[str, Any]:
        """
        Collecte les utilisateurs locaux Windows

        Returns:
            dict: Informations utilisateurs locaux
        """
        users_info = {
            'local_users': [],
            'total_users': 0
        }

        try:
            import wmi
            c = wmi.WMI()

            for user in c.Win32_UserAccount(LocalAccount=True):
                user_info = {
                    'name': self._clean_string(user.Name),
                    'full_name': self._clean_string(user.FullName),
                    'description': self._clean_string(user.Description),
                    'disabled': user.Disabled,
                    'locked_out': user.Lockout,
                    'password_required': user.PasswordRequired,
                    'password_changeable': user.PasswordChangeable,
                    'password_expires': user.PasswordExpires,
                    'account_type': user.AccountType,
                    'sid': self._clean_string(user.SID)
                }
                users_info['local_users'].append(user_info)

            users_info['total_users'] = len(users_info['local_users'])

        except ImportError:
            self.logger.warning("Module WMI non disponible pour utilisateurs")
        except Exception as e:
            self.logger.error(f"Erreur collecte utilisateurs Windows: {e}")

        return users_info

    def _collect_windows_environment(self) -> Dict[str, Any]:
        """
        Collecte les variables d'environnement spécifiques Windows

        Returns:
            dict: Variables d'environnement Windows
        """
        env_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Variables d'environnement système
            system_env = {}
            for env_var in c.Win32_Environment(SystemVariable=True):
                var_name = env_var.Name
                var_value = env_var.VariableValue
                if var_name and var_value:
                    # Tronquer les valeurs très longues
                    if len(var_value) > 200:
                        var_value = var_value[:200] + "..."
                    system_env[var_name] = var_value

            env_info['system_variables'] = system_env

            # Variables d'environnement utilisateur courrant
            user_env = {}
            for env_var in c.Win32_Environment(SystemVariable=False):
                var_name = env_var.Name
                var_value = env_var.VariableValue
                if var_name and var_value:
                    if len(var_value) > 200:
                        var_value = var_value[:200] + "..."
                    user_env[var_name] = var_value

            env_info['user_variables'] = user_env

        except ImportError:
            self.logger.warning("Module WMI non disponible pour environnement")
        except Exception as e:
            self.logger.error(f"Erreur collecte environnement Windows: {e}")

        return env_info

    def _collect_boot_info(self) -> Dict[str, Any]:
        """
        Collecte les informations de démarrage Windows

        Returns:
            dict: Informations de démarrage
        """
        boot_info = {}

        try:
            import wmi
            c = wmi.WMI()

            # Configuration de démarrage
            for boot_config in c.Win32_BootConfiguration():
                boot_info['boot_directory'] = self._clean_string(boot_config.BootDirectory)
                boot_info['config_path'] = self._clean_string(boot_config.ConfigurationPath)
                boot_info['temp_directory'] = self._clean_string(boot_config.TempDirectory)
                break

            # Informations démarrage depuis le système
            for os_info in c.Win32_OperatingSystem():
                boot_info['last_boot_time'] = os_info.LastBootUpTime
                boot_info['system_up_time'] = os_info.SystemUpTime
                break

        except ImportError:
            self.logger.warning("Module WMI non disponible pour démarrage")
        except Exception as e:
            self.logger.error(f"Erreur collecte démarrage Windows: {e}")

        return boot_info