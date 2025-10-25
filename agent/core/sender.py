"""
Module de communication avec le serveur pour l'agent d'inventaire

Ce module gère :
- L'envoi des données d'inventaire au serveur central
- L'authentification
- La gestion des erreurs réseau
- Les tentatives de reconnexion
"""

import json
import time
import requests
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import urllib3

# Désactiver les warnings SSL si nécessaire
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class InventorySender:
    """
    Gestionnaire de communication avec le serveur central

    Cette classe s'occupe de l'envoi sécurisé des données d'inventaire
    vers le serveur central avec gestion d'erreurs et reconnexion automatique.
    """

    def __init__(self, config, logger):
        """
        Initialise le sender avec la configuration

        Args:
            config: Instance de AgentConfig
            logger: Instance de AgentLogger
        """
        self.config = config
        self.logger = logger.get_logger()

        # Configuration serveur
        server_config = config.get_server_config()
        self.server_url = server_config['url']
        self.auth_token = server_config['auth_token']
        self.timeout = server_config['timeout']
        self.verify_ssl = server_config['verify_ssl']

        # Statistiques de communication
        self.last_successful_send = None
        self.send_attempts = 0
        self.send_failures = 0

        self.logger.info("InventorySender initialisé")
        self.logger.info(f"URL serveur: {self.server_url}")

    def send_inventory(self, inventory_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Envoie les données d'inventaire au serveur

        Args:
            inventory_data: Dictionnaire contenant les données d'inventaire

        Returns:
            Tuple[bool, str]: (Succès, Message de résultat)
        """
        self.send_attempts += 1

        try:
            self.logger.info("Début de l'envoi d'inventaire au serveur")

            # Préparer les headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'WatchmanAgentClient/1.0.0'
            }

            # Ajouter l'authentification si configurée
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'
                self.logger.debug("Token d'authentification ajouté")

            # Ajouter des métadonnées à l'envoi
            payload = {
                'timestamp': datetime.now().isoformat(),
                'agent_version': '1.0.0',
                'data': inventory_data
            }

            self.logger.debug(f"Taille des données: {len(json.dumps(payload))} bytes")

            # Effectuer la requête HTTP POST
            response = requests.post(
                url=self.server_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )

            # Vérifier le code de statut
            if response.status_code == 201:
                self.last_successful_send = datetime.now()
                self.logger.info("Inventaire envoyé avec succès")

                # Tenter de parser la réponse serveur
                try:
                    server_response = response.json()
                    server_message = server_response.get('message', 'Succès')
                    self.logger.debug(f"Réponse serveur: {server_message}")
                    return True, f"Envoi réussi: {server_message}"
                except json.JSONDecodeError:
                    return True, "Envoi réussi (réponse serveur non-JSON)"

            elif response.status_code == 401:
                self.send_failures += 1
                error_msg = "Erreur d'authentification (token invalide ou manquant)"
                self.logger.error(error_msg)
                return False, error_msg

            elif response.status_code == 403:
                self.send_failures += 1
                error_msg = "Accès refusé par le serveur"
                self.logger.error(error_msg)
                return False, error_msg

            elif response.status_code == 400:
                self.send_failures += 1
                error_msg = f"Données invalides: {response.text[:200]}"
                self.logger.error(error_msg)
                return False, error_msg

            else:
                self.send_failures += 1
                error_msg = f"Erreur serveur HTTP {response.status_code}: {response.text[:200]}"
                self.logger.error(error_msg)
                return False, error_msg

        except requests.exceptions.Timeout:
            self.send_failures += 1
            error_msg = f"Timeout lors de l'envoi (>{self.timeout}s)"
            self.logger.error(error_msg)
            return False, error_msg

        except requests.exceptions.ConnectionError as e:
            self.send_failures += 1
            error_msg = f"Erreur de connexion: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

        except requests.exceptions.SSLError as e:
            self.send_failures += 1
            error_msg = f"Erreur SSL: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            self.send_failures += 1
            error_msg = f"Erreur inattendue: {str(e)}"
            self.logger.exception("Erreur lors de l'envoi d'inventaire")
            return False, error_msg

    def send_inventory_with_retry(self, inventory_data: Dict[str, Any],
                                 max_retries: int = 3,
                                 retry_delay: int = 5) -> Tuple[bool, str]:
        """
        Envoie l'inventaire avec tentatives de reconnexion

        Args:
            inventory_data: Données d'inventaire à envoyer
            max_retries: Nombre maximum de tentatives
            retry_delay: Délai entre les tentatives (secondes)

        Returns:
            Tuple[bool, str]: (Succès final, Message de résultat)
        """
        last_error = ""

        for attempt in range(max_retries + 1):
            if attempt > 0:
                self.logger.info(f"Tentative {attempt + 1}/{max_retries + 1}")
                time.sleep(retry_delay)

            success, message = self.send_inventory(inventory_data)

            if success:
                if attempt > 0:
                    self.logger.info(f"Envoi réussi après {attempt + 1} tentative(s)")
                return True, message

            last_error = message

            # Ne pas attendre après la dernière tentative
            if attempt < max_retries:
                self.logger.warning(f"Tentative {attempt + 1} échouée: {message}")
                self.logger.info(f"Nouvelle tentative dans {retry_delay} secondes...")

        # Toutes les tentatives ont échoué
        self.logger.error(f"Échec définitif après {max_retries + 1} tentatives")
        return False, f"Échec après {max_retries + 1} tentatives. Dernière erreur: {last_error}"

    def test_connection(self) -> Tuple[bool, str]:
        """
        Teste la connexion au serveur sans envoyer de données

        Returns:
            Tuple[bool, str]: (Connexion OK, Message de statut)
        """
        try:
            self.logger.info("Test de connexion au serveur...")

            # Essayer une requête GET ou HEAD simple
            test_url = self.server_url.replace('/api/v1/inventory', '/health')
            if test_url == self.server_url:
                # Si pas de endpoint health, utiliser l'endpoint principal
                test_url = self.server_url

            headers = {'User-Agent': 'WatchmanAgentClient/1.0.0'}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'

            response = requests.get(
                url=test_url,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )

            if response.status_code in [200, 404, 405]:  # 404/405 = serveur répond mais endpoint inexistant
                self.logger.info("Connexion au serveur réussie")
                return True, "Connexion OK"
            else:
                error_msg = f"Serveur répond avec code {response.status_code}"
                self.logger.warning(error_msg)
                return False, error_msg

        except requests.exceptions.Timeout:
            error_msg = "Timeout lors du test de connexion"
            self.logger.error(error_msg)
            return False, error_msg

        except requests.exceptions.ConnectionError:
            error_msg = "Impossible de se connecter au serveur"
            self.logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Erreur lors du test: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de communication

        Returns:
            dict: Statistiques d'envoi
        """
        return {
            'last_successful_send': self.last_successful_send.isoformat() if self.last_successful_send else None,
            'total_attempts': self.send_attempts,
            'total_failures': self.send_failures,
            'success_rate': ((self.send_attempts - self.send_failures) / self.send_attempts * 100) if self.send_attempts > 0 else 0,
            'server_url': self.server_url
        }

    def update_config(self, config):
        """
        Met à jour la configuration du sender

        Args:
            config: Nouvelle configuration
        """
        self.config = config
        server_config = config.get_server_config()

        self.server_url = server_config['url']
        self.auth_token = server_config['auth_token']
        self.timeout = server_config['timeout']
        self.verify_ssl = server_config['verify_ssl']

        self.logger.info("Configuration du sender mise à jour")
        self.logger.info(f"Nouvelle URL serveur: {self.server_url}")