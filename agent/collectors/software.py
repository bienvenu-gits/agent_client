"""
Collecteur de logiciels installés pour l'agent d'inventaire

Ce module collecte la liste des applications et logiciels installés :
- Applications installées via le gestionnaire de paquets système
- Logiciels installés manuellement
- Versions et informations détaillées
- Support multi-plateforme (Windows, Linux, macOS)
"""

import sys
import re
import json
from typing import List, Dict, Any, Optional

from .base import BaseCollector


class SoftwareCollector(BaseCollector):
    """
    Collecteur de logiciels installés

    Ce collecteur utilise différentes méthodes selon la plateforme
    pour récupérer la liste complète des logiciels installés.
    """

    def collect(self) -> List[Dict[str, Any]]:
        """
        Collecte tous les logiciels installés

        Returns:
            list: Liste des applications avec leurs détails
        """
        self._start_collection()

        applications = []

        # Ajouter le système d'exploitation comme première "application"
        os_info = self._get_os_application()
        if os_info:
            applications.append(os_info)

        # Collecte spécifique à la plateforme
        if sys.platform == "win32":
            applications.extend(self._collect_windows_software())
        elif sys.platform == "darwin":
            applications.extend(self._collect_macos_software())
        else:
            applications.extend(self._collect_linux_software())

        # Ajouter des logiciels détectés via des méthodes génériques
        applications.extend(self._collect_generic_software())

        # Nettoyer et déduplicater
        applications = self._cleanup_applications(applications)

        self.logger.info(f"Collecté {len(applications)} applications")
        self.last_collection_duration = self._end_collection()

        return applications

    def _get_os_application(self) -> Optional[Dict[str, Any]]:
        """
        Crée une entrée pour le système d'exploitation

        Returns:
            dict: Informations OS formatées comme une application
        """
        try:
            import platform

            if sys.platform == "win32":
                # Windows
                os_name = "Microsoft Windows"
                os_version = platform.release()
                os_vendor = "Microsoft Corporation"

                # Essayer de récupérer la version détaillée
                try:
                    version_info = platform.win32_ver()
                    if version_info[1]:
                        os_version = version_info[1]
                except Exception:
                    pass

            elif sys.platform == "darwin":
                # macOS
                os_name = "macOS"
                mac_version = platform.mac_ver()[0]
                os_version = mac_version if mac_version else platform.release()
                os_vendor = "Apple Inc."

            else:
                # Linux et autres Unix
                os_name = platform.system()
                os_version = platform.release()
                os_vendor = "Open Source"

                # Essayer de récupérer des infos plus précises depuis /etc/os-release
                try:
                    with open('/etc/os-release', 'r') as f:
                        lines = f.readlines()

                    os_info = {}
                    for line in lines:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            os_info[key] = value.strip('"')

                    if 'NAME' in os_info:
                        os_name = os_info['NAME']
                    if 'VERSION' in os_info:
                        os_version = os_info['VERSION']

                except FileNotFoundError:
                    pass

            return {
                'name': os_name,
                'version': self._parse_version(os_version),
                'vendor': os_vendor,
                'type': 'os'
            }

        except Exception as e:
            self.logger.warning(f"Erreur récupération infos OS: {e}")
            return None

    def _collect_windows_software(self) -> List[Dict[str, Any]]:
        """
        Collecte les logiciels installés sur Windows

        Returns:
            list: Applications Windows
        """
        applications = []

        # Méthode 1: WMI
        wmi_apps = self._collect_windows_wmi()
        applications.extend(wmi_apps)

        # Méthode 2: Registre Windows
        registry_apps = self._collect_windows_registry()
        applications.extend(registry_apps)

        # Méthode 3: PowerShell (si disponible)
        ps_apps = self._collect_windows_powershell()
        applications.extend(ps_apps)

        return applications

    def _collect_windows_wmi(self) -> List[Dict[str, Any]]:
        """
        Utilise WMI pour récupérer les logiciels Windows

        Returns:
            list: Applications via WMI
        """
        applications = []

        try:
            import wmi
            c = wmi.WMI()

            # Récupérer via Win32_Product (peut être lent)
            for product in c.Win32_Product():
                app = {
                    'name': self._clean_string(product.Name),
                    'version': self._parse_version(product.Version),
                    'vendor': self._clean_string(product.Vendor),
                    'type': 'application'
                }
                applications.append(app)

            self.logger.debug(f"WMI: {len(applications)} applications trouvées")

        except ImportError:
            self.logger.debug("Module WMI non disponible")
        except Exception as e:
            self.logger.warning(f"Erreur WMI: {e}")

        return applications

    def _collect_windows_registry(self) -> List[Dict[str, Any]]:
        """
        Lit le registre Windows pour les applications installées

        Returns:
            list: Applications via registre
        """
        applications = []

        try:
            import winreg

            # Clés de registre à vérifier
            registry_paths = [
                r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
                r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
            ]

            for path in registry_paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
                    applications.extend(self._read_registry_software(key))
                    winreg.CloseKey(key)
                except Exception as e:
                    self.logger.debug(f"Erreur lecture registre {path}: {e}")

            self.logger.debug(f"Registre: {len(applications)} applications trouvées")

        except ImportError:
            self.logger.debug("Module winreg non disponible")
        except Exception as e:
            self.logger.warning(f"Erreur registre: {e}")

        return applications

    def _read_registry_software(self, key) -> List[Dict[str, Any]]:
        """
        Lit les applications d'une clé de registre

        Args:
            key: Clé de registre ouverte

        Returns:
            list: Applications trouvées
        """
        import winreg
        applications = []

        try:
            # Parcourir toutes les sous-clés
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)

                    # Lire les informations de l'application
                    app_info = {}

                    try:
                        app_info['name'] = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    except FileNotFoundError:
                        # Pas de nom d'affichage, ignorer
                        winreg.CloseKey(subkey)
                        i += 1
                        continue

                    try:
                        app_info['version'] = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                    except FileNotFoundError:
                        app_info['version'] = "Unknown"

                    try:
                        app_info['vendor'] = winreg.QueryValueEx(subkey, "Publisher")[0]
                    except FileNotFoundError:
                        app_info['vendor'] = "Unknown"

                    # Nettoyer et ajouter
                    if app_info['name'] and app_info['name'].strip():
                        applications.append({
                            'name': self._clean_string(app_info['name']),
                            'version': self._parse_version(app_info['version']),
                            'vendor': self._clean_string(app_info['vendor']),
                            'type': 'application'
                        })

                    winreg.CloseKey(subkey)
                    i += 1

                except OSError:
                    # Plus de sous-clés
                    break

        except Exception as e:
            self.logger.warning(f"Erreur lecture sous-clés registre: {e}")

        return applications

    def _collect_windows_powershell(self) -> List[Dict[str, Any]]:
        """
        Utilise PowerShell pour récupérer les applications

        Returns:
            list: Applications via PowerShell
        """
        applications = []

        # Commande PowerShell pour récupérer les applications
        ps_command = (
            "Get-WmiObject -Class Win32_Product | "
            "Select-Object Name, Version, Vendor | "
            "ConvertTo-Json"
        )

        try:
            output = self._execute_command(f'powershell -Command "{ps_command}"')
            if output:
                apps_data = json.loads(output)

                # Gérer le cas d'un seul élément (pas de liste)
                if isinstance(apps_data, dict):
                    apps_data = [apps_data]

                for app_data in apps_data:
                    if app_data.get('Name'):
                        applications.append({
                            'name': self._clean_string(app_data['Name']),
                            'version': self._parse_version(app_data.get('Version', 'Unknown')),
                            'vendor': self._clean_string(app_data.get('Vendor', 'Unknown')),
                            'type': 'application'
                        })

            self.logger.debug(f"PowerShell: {len(applications)} applications trouvées")

        except Exception as e:
            self.logger.debug(f"Erreur PowerShell: {e}")

        return applications

    def _collect_macos_software(self) -> List[Dict[str, Any]]:
        """
        Collecte les logiciels installés sur macOS

        Returns:
            list: Applications macOS
        """
        applications = []

        # Méthode 1: Applications dans /Applications
        apps_folder = self._collect_macos_applications_folder()
        applications.extend(apps_folder)

        # Méthode 2: Homebrew
        homebrew_apps = self._collect_macos_homebrew()
        applications.extend(homebrew_apps)

        # Méthode 3: system_profiler
        profiler_apps = self._collect_macos_system_profiler()
        applications.extend(profiler_apps)

        return applications

    def _collect_macos_applications_folder(self) -> List[Dict[str, Any]]:
        """
        Scan du dossier /Applications sur macOS

        Returns:
            list: Applications du dossier Applications
        """
        applications = []

        try:
            import os
            import plistlib

            apps_path = "/Applications"
            if os.path.exists(apps_path):
                for item in os.listdir(apps_path):
                    if item.endswith('.app'):
                        app_path = os.path.join(apps_path, item)
                        plist_path = os.path.join(app_path, 'Contents', 'Info.plist')

                        if os.path.exists(plist_path):
                            try:
                                with open(plist_path, 'rb') as f:
                                    plist_data = plistlib.load(f)

                                app_name = plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName', item[:-4])
                                app_version = plist_data.get('CFBundleShortVersionString', 'Unknown')
                                app_vendor = plist_data.get('CFBundleIdentifier', 'Unknown')

                                # Extraire le vendor du bundle identifier
                                if '.' in app_vendor:
                                    vendor_parts = app_vendor.split('.')
                                    if len(vendor_parts) >= 2:
                                        app_vendor = vendor_parts[1].title()

                                applications.append({
                                    'name': self._clean_string(app_name),
                                    'version': self._parse_version(app_version),
                                    'vendor': self._clean_string(app_vendor),
                                    'type': 'application'
                                })

                            except Exception as e:
                                self.logger.debug(f"Erreur lecture plist {plist_path}: {e}")

            self.logger.debug(f"Dossier Applications: {len(applications)} applications trouvées")

        except Exception as e:
            self.logger.warning(f"Erreur scan dossier Applications: {e}")

        return applications

    def _collect_macos_homebrew(self) -> List[Dict[str, Any]]:
        """
        Collecte les packages Homebrew sur macOS

        Returns:
            list: Packages Homebrew
        """
        applications = []

        try:
            # Liste des packages Homebrew
            output = self._execute_command("brew list --versions")
            if output:
                for line in output.split('\n'):
                    if line.strip():
                        parts = line.strip().split(' ', 1)
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]

                            applications.append({
                                'name': self._clean_string(name),
                                'version': self._parse_version(version),
                                'vendor': 'Homebrew',
                                'type': 'package'
                            })

            self.logger.debug(f"Homebrew: {len(applications)} packages trouvés")

        except Exception as e:
            self.logger.debug(f"Erreur Homebrew: {e}")

        return applications

    def _collect_macos_system_profiler(self) -> List[Dict[str, Any]]:
        """
        Utilise system_profiler pour récupérer les applications

        Returns:
            list: Applications via system_profiler
        """
        applications = []

        try:
            output = self._execute_command("system_profiler SPApplicationsDataType -json")
            if output:
                data = json.loads(output)
                apps_data = data.get('SPApplicationsDataType', [])

                for app_data in apps_data:
                    name = app_data.get('_name', '')
                    version = app_data.get('version', 'Unknown')
                    vendor = app_data.get('obtained_from', 'Unknown')

                    if name:
                        applications.append({
                            'name': self._clean_string(name),
                            'version': self._parse_version(version),
                            'vendor': self._clean_string(vendor),
                            'type': 'application'
                        })

            self.logger.debug(f"system_profiler: {len(applications)} applications trouvées")

        except Exception as e:
            self.logger.debug(f"Erreur system_profiler: {e}")

        return applications

    def _collect_linux_software(self) -> List[Dict[str, Any]]:
        """
        Collecte les logiciels installés sur Linux

        Returns:
            list: Applications Linux
        """
        applications = []

        # Méthode 1: dpkg (Debian/Ubuntu)
        dpkg_apps = self._collect_linux_dpkg()
        applications.extend(dpkg_apps)

        # Méthode 2: rpm (RedHat/CentOS/Fedora)
        rpm_apps = self._collect_linux_rpm()
        applications.extend(rpm_apps)

        # Méthode 3: pacman (Arch Linux)
        pacman_apps = self._collect_linux_pacman()
        applications.extend(pacman_apps)

        # Méthode 4: Snap packages
        snap_apps = self._collect_linux_snap()
        applications.extend(snap_apps)

        # Méthode 5: Flatpak
        flatpak_apps = self._collect_linux_flatpak()
        applications.extend(flatpak_apps)

        return applications

    def _collect_linux_dpkg(self) -> List[Dict[str, Any]]:
        """
        Collecte via dpkg (Debian/Ubuntu)

        Returns:
            list: Packages dpkg
        """
        applications = []

        try:
            output = self._execute_command("dpkg -l")
            if output:
                for line in output.split('\n'):
                    if line.startswith('ii '):  # Installé
                        parts = line.split()
                        if len(parts) >= 3:
                            name = parts[1]
                            version = parts[2]

                            applications.append({
                                'name': self._clean_string(name),
                                'version': self._parse_version(version),
                                'vendor': 'Debian Package',
                                'type': 'package'
                            })

            self.logger.debug(f"dpkg: {len(applications)} packages trouvés")

        except Exception as e:
            self.logger.debug(f"Erreur dpkg: {e}")

        return applications

    def _collect_linux_rpm(self) -> List[Dict[str, Any]]:
        """
        Collecte via rpm (RedHat/CentOS/Fedora)

        Returns:
            list: Packages RPM
        """
        applications = []

        try:
            output = self._execute_command("rpm -qa --queryformat '%{NAME} %{VERSION}-%{RELEASE}\\n'")
            if output:
                for line in output.split('\n'):
                    if line.strip():
                        parts = line.strip().split(' ', 1)
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]

                            applications.append({
                                'name': self._clean_string(name),
                                'version': self._parse_version(version),
                                'vendor': 'RPM Package',
                                'type': 'package'
                            })

            self.logger.debug(f"rpm: {len(applications)} packages trouvés")

        except Exception as e:
            self.logger.debug(f"Erreur rpm: {e}")

        return applications

    def _collect_linux_pacman(self) -> List[Dict[str, Any]]:
        """
        Collecte via pacman (Arch Linux)

        Returns:
            list: Packages pacman
        """
        applications = []

        try:
            output = self._execute_command("pacman -Q")
            if output:
                for line in output.split('\n'):
                    if line.strip():
                        parts = line.strip().split(' ')
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]

                            applications.append({
                                'name': self._clean_string(name),
                                'version': self._parse_version(version),
                                'vendor': 'Arch Package',
                                'type': 'package'
                            })

            self.logger.debug(f"pacman: {len(applications)} packages trouvés")

        except Exception as e:
            self.logger.debug(f"Erreur pacman: {e}")

        return applications

    def _collect_linux_snap(self) -> List[Dict[str, Any]]:
        """
        Collecte les packages Snap

        Returns:
            list: Packages Snap
        """
        applications = []

        try:
            output = self._execute_command("snap list")
            if output:
                lines = output.split('\n')[1:]  # Ignorer l'en-tête
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]

                            applications.append({
                                'name': self._clean_string(name),
                                'version': self._parse_version(version),
                                'vendor': 'Snap Package',
                                'type': 'snap'
                            })

            self.logger.debug(f"snap: {len(applications)} packages trouvés")

        except Exception as e:
            self.logger.debug(f"Erreur snap: {e}")

        return applications

    def _collect_linux_flatpak(self) -> List[Dict[str, Any]]:
        """
        Collecte les packages Flatpak

        Returns:
            list: Packages Flatpak
        """
        applications = []

        try:
            output = self._execute_command("flatpak list --app --columns=name,version")
            if output:
                for line in output.split('\n'):
                    if line.strip() and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1] if parts[1] else 'Unknown'

                            applications.append({
                                'name': self._clean_string(name),
                                'version': self._parse_version(version),
                                'vendor': 'Flatpak',
                                'type': 'flatpak'
                            })

            self.logger.debug(f"flatpak: {len(applications)} packages trouvés")

        except Exception as e:
            self.logger.debug(f"Erreur flatpak: {e}")

        return applications

    def _collect_generic_software(self) -> List[Dict[str, Any]]:
        """
        Collecte via des méthodes génériques multi-plateforme

        Returns:
            list: Applications détectées génériquement
        """
        applications = []

        # Python packages installés
        python_packages = self._collect_python_packages()
        applications.extend(python_packages)

        return applications

    def _collect_python_packages(self) -> List[Dict[str, Any]]:
        """
        Collecte les packages Python installés

        Returns:
            list: Packages Python
        """
        applications = []

        try:
            # Utiliser pip list
            output = self._execute_command("pip list --format=json")
            if output:
                packages = json.loads(output)
                for package in packages:
                    applications.append({
                        'name': f"Python: {package['name']}",
                        'version': self._parse_version(package['version']),
                        'vendor': 'Python Package',
                        'type': 'python_package'
                    })

            self.logger.debug(f"Python packages: {len(applications)} packages trouvés")

        except Exception as e:
            self.logger.debug(f"Erreur Python packages: {e}")

        return applications

    def _cleanup_applications(self, applications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Nettoie et déduplique la liste des applications

        Args:
            applications: Liste brute des applications

        Returns:
            list: Liste nettoyée et dédupliquée
        """
        # Déduplication basée sur nom + version
        seen = set()
        cleaned_apps = []

        for app in applications:
            # Créer une clé unique
            key = f"{app['name'].lower()}_{app['version']}"

            if key not in seen and app['name'].strip():
                seen.add(key)
                cleaned_apps.append(app)

        # Trier par nom
        cleaned_apps.sort(key=lambda x: x['name'].lower())

        return cleaned_apps