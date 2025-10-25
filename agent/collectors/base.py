"""
Classe de base pour tous les collecteurs de l'agent d'inventaire

Ce module définit l'interface commune que tous les collecteurs
doivent implémenter, ainsi que des utilitaires partagés.
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Union, Optional


class BaseCollector(ABC):
    """
    Classe de base abstraite pour tous les collecteurs

    Cette classe définit l'interface commune et fournit des méthodes
    utilitaires pour la collecte de données système.
    """

    def __init__(self, config, logger):
        """
        Initialise le collecteur de base

        Args:
            config: Instance de AgentConfig
            logger: Instance de AgentLogger
        """
        self.config = config
        self.logger = logger

        # Métadonnées du collecteur
        self.collector_name = self.__class__.__name__
        self.collection_start_time = None
        self.collection_errors = []

    @abstractmethod
    def collect(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Méthode principale de collecte - doit être implémentée par chaque collecteur

        Returns:
            Union[Dict, List]: Données collectées
        """
        pass

    def _start_collection(self):
        """
        Démarre une session de collecte

        Initialise les métriques et logs pour le suivi de performance.
        """
        self.collection_start_time = time.time()
        self.collection_errors = []
        self.logger.debug(f"Début collecte {self.collector_name}")

    def _end_collection(self) -> float:
        """
        Termine une session de collecte

        Returns:
            float: Durée de collecte en secondes
        """
        if self.collection_start_time:
            duration = time.time() - self.collection_start_time
            self.logger.debug(f"Collecte {self.collector_name} terminée en {duration:.2f}s")

            if self.collection_errors:
                self.logger.warning(f"Collecte {self.collector_name} avec {len(self.collection_errors)} erreur(s)")

            return duration
        return 0.0

    def _safe_execute(self, func, error_message: str = "Erreur lors de l'exécution", default_value=None):
        """
        Exécute une fonction de manière sécurisée avec gestion d'erreur

        Args:
            func: Fonction à exécuter
            error_message: Message d'erreur personnalisé
            default_value: Valeur par défaut en cas d'erreur

        Returns:
            Résultat de la fonction ou default_value
        """
        try:
            return func()
        except Exception as e:
            error_details = f"{error_message}: {str(e)}"
            self.collection_errors.append(error_details)
            self.logger.warning(error_details)
            return default_value

    def _format_bytes(self, bytes_value: int) -> str:
        """
        Formate une valeur en bytes en format lisible

        Args:
            bytes_value: Valeur en bytes

        Returns:
            str: Valeur formatée (ex: "1.5 GB")
        """
        if bytes_value is None:
            return "N/A"

        try:
            bytes_value = int(bytes_value)
        except (ValueError, TypeError):
            return "N/A"

        # Unités
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(bytes_value)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.1f} {units[unit_index]}"

    def _format_frequency(self, hz_value: Union[int, float]) -> str:
        """
        Formate une fréquence en Hz vers un format lisible

        Args:
            hz_value: Fréquence en Hz

        Returns:
            str: Fréquence formatée (ex: "2.4 GHz")
        """
        if hz_value is None:
            return "N/A"

        try:
            hz_value = float(hz_value)
        except (ValueError, TypeError):
            return "N/A"

        # Unités de fréquence
        if hz_value >= 1_000_000_000:  # GHz
            return f"{hz_value / 1_000_000_000:.1f} GHz"
        elif hz_value >= 1_000_000:  # MHz
            return f"{hz_value / 1_000_000:.1f} MHz"
        elif hz_value >= 1_000:  # KHz
            return f"{hz_value / 1_000:.1f} KHz"
        else:
            return f"{hz_value:.0f} Hz"

    def _clean_string(self, value: str) -> str:
        """
        Nettoie une chaîne de caractères

        Args:
            value: Chaîne à nettoyer

        Returns:
            str: Chaîne nettoyée
        """
        if not value:
            return ""

        # Convertir en string si nécessaire
        value = str(value)

        # Supprimer les espaces en début/fin
        value = value.strip()

        # Supprimer les caractères de contrôle
        value = ''.join(char for char in value if char.isprintable())

        # Supprimer les espaces multiples
        import re
        value = re.sub(r'\s+', ' ', value)

        return value

    def _get_safe_attribute(self, obj, attribute: str, default="N/A"):
        """
        Récupère un attribut d'un objet de manière sécurisée

        Args:
            obj: Objet source
            attribute: Nom de l'attribut
            default: Valeur par défaut

        Returns:
            Valeur de l'attribut ou default
        """
        try:
            if hasattr(obj, attribute):
                value = getattr(obj, attribute)
                if value is None:
                    return default
                return value
            return default
        except Exception:
            return default

    def _execute_command(self, command: str) -> Optional[str]:
        """
        Exécute une commande système et retourne le résultat

        Args:
            command: Commande à exécuter

        Returns:
            str: Sortie de la commande ou None en cas d'erreur
        """
        try:
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30  # Timeout de 30 secondes
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                self.logger.warning(f"Commande échouée: {command} (code: {result.returncode})")
                return None

        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout pour la commande: {command}")
            return None
        except Exception as e:
            self.logger.warning(f"Erreur lors de l'exécution de '{command}': {e}")
            return None

    def _read_file(self, file_path: str) -> Optional[str]:
        """
        Lit un fichier de manière sécurisée

        Args:
            file_path: Chemin vers le fichier

        Returns:
            str: Contenu du fichier ou None
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            self.logger.debug(f"Fichier non trouvé: {file_path}")
            return None
        except Exception as e:
            self.logger.warning(f"Erreur lecture fichier {file_path}: {e}")
            return None

    def _parse_version(self, version_string: str) -> str:
        """
        Parse et nettoie une chaîne de version

        Args:
            version_string: Chaîne de version brute

        Returns:
            str: Version nettoyée
        """
        if not version_string:
            return "Unknown"

        version_string = str(version_string).strip()

        # Supprimer les préfixes communs
        prefixes_to_remove = ['version ', 'v', 'Version ', 'V']
        for prefix in prefixes_to_remove:
            if version_string.lower().startswith(prefix.lower()):
                version_string = version_string[len(prefix):].strip()

        # Garder seulement les caractères de version valides
        import re
        version_match = re.search(r'[\d\.\-\w]+', version_string)
        if version_match:
            return version_match.group(0)

        return version_string if version_string else "Unknown"

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la dernière collecte

        Returns:
            dict: Statistiques du collecteur
        """
        return {
            'collector_name': self.collector_name,
            'collection_duration': getattr(self, 'last_collection_duration', 0),
            'errors_count': len(self.collection_errors),
            'errors': self.collection_errors.copy()
        }