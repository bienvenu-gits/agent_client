"""
Application Flask pour l'interface web de l'agent d'inventaire

Cette application fournit une interface web simple et efficace
permettant de contrôler l'agent d'inventaire localement.
"""

import os
import sys
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import threading
import logging

# Ajouter le chemin parent pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.core.config import AgentConfig
from agent.core.logger import AgentLogger
from agent.core.collector import InventoryCollector
from agent.core.sender import InventorySender
from agent.core.scheduler import InventoryScheduler


class InventoryWebApp:
    """
    Application web Flask pour l'agent d'inventaire

    Cette classe encapsule l'application Flask et fournit les routes
    et fonctionnalités nécessaires pour l'interface web.
    """

    def __init__(self, config_path=None):
        """
        Initialise l'application web

        Args:
            config_path: Chemin vers le fichier de configuration
        """
        # Configuration
        self.config = AgentConfig(config_path)

        # Logger
        self.logger = AgentLogger(self.config)
        self.app_logger = self.logger.get_logger()

        # Composants de l'agent
        self.collector = InventoryCollector(self.config, self.logger)
        self.sender = InventorySender(self.config, self.logger)
        self.scheduler = None

        # Application Flask
        self.app = Flask(__name__)
        self.app.secret_key = 'watchman_agent_client_secret_key_change_in_production'

        # Désactiver les logs Flask pour éviter la pollution
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        # État de l'application
        self.app_status = {
            'last_collection': None,
            'last_collection_time': None,
            'last_send_result': None,
            'last_send_time': None,
            'collection_in_progress': False,
            'send_in_progress': False
        }

        # Enregistrer les routes
        self._register_routes()

        self.app_logger.info("Interface web initialisée")

    def _register_routes(self):
        """
        Enregistre toutes les routes Flask

        Configure toutes les routes de l'interface web avec leurs
        handlers respectifs.
        """
        # Page d'accueil - Page unique simple
        @self.app.route('/')
        def index():
            """Page unique simple avec logo et bouton collecter+envoyer"""
            try:
                # Récupérer les informations de statut minimales
                status_info = self._get_status_info()

                return render_template('index.html', status=status_info)

            except Exception as e:
                self.app_logger.error(f"Erreur page index: {e}")
                return f"Erreur: {str(e)}", 500

        # API pour forcer une collecte d'inventaire
        @self.app.route('/api/collect', methods=['POST'])
        def api_collect():
            """API pour déclencher une collecte d'inventaire"""
            try:
                if self.app_status['collection_in_progress']:
                    return jsonify({
                        'success': False,
                        'message': 'Une collecte est déjà en cours'
                    }), 400

                # Démarrer la collecte en arrière-plan
                def collect_background():
                    try:
                        self.app_status['collection_in_progress'] = True
                        self.app_logger.info("Démarrage collecte forcée via web")

                        # Effectuer la collecte
                        inventory_data = self.collector.collect_all(force_refresh=True)

                        # Stocker le résultat
                        self.app_status['last_collection'] = inventory_data
                        self.app_status['last_collection_time'] = datetime.now()

                        self.app_logger.info("Collecte forcée terminée avec succès")

                    except Exception as e:
                        self.app_logger.error(f"Erreur collecte forcée: {e}")
                    finally:
                        self.app_status['collection_in_progress'] = False

                # Lancer en thread
                collect_thread = threading.Thread(target=collect_background, daemon=True)
                collect_thread.start()

                return jsonify({
                    'success': True,
                    'message': 'Collecte d\'inventaire démarrée'
                })

            except Exception as e:
                self.app_logger.error(f"Erreur API collect: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Erreur: {str(e)}'
                }), 500

        # API pour envoyer l'inventaire au serveur
        @self.app.route('/api/send', methods=['POST'])
        def api_send():
            """API pour envoyer l'inventaire au serveur"""
            try:
                if self.app_status['send_in_progress']:
                    return jsonify({
                        'success': False,
                        'message': 'Un envoi est déjà en cours'
                    }), 400

                if not self.app_status['last_collection']:
                    return jsonify({
                        'success': False,
                        'message': 'Aucune donnée d\'inventaire à envoyer. Effectuez d\'abord une collecte.'
                    }), 400

                # Démarrer l'envoi en arrière-plan
                def send_background():
                    try:
                        self.app_status['send_in_progress'] = True
                        self.app_logger.info("Démarrage envoi forcé via web")

                        # Envoyer les données
                        success, message = self.sender.send_inventory_with_retry(
                            self.app_status['last_collection'],
                            max_retries=2
                        )

                        # Stocker le résultat
                        self.app_status['last_send_result'] = {
                            'success': success,
                            'message': message
                        }
                        self.app_status['last_send_time'] = datetime.now()

                        if success:
                            self.app_logger.info("Envoi forcé terminé avec succès")
                        else:
                            self.app_logger.error(f"Envoi forcé échoué: {message}")

                    except Exception as e:
                        self.app_logger.error(f"Erreur envoi forcé: {e}")
                        self.app_status['last_send_result'] = {
                            'success': False,
                            'message': str(e)
                        }
                    finally:
                        self.app_status['send_in_progress'] = False

                # Lancer en thread
                send_thread = threading.Thread(target=send_background, daemon=True)
                send_thread.start()

                return jsonify({
                    'success': True,
                    'message': 'Envoi d\'inventaire démarré'
                })

            except Exception as e:
                self.app_logger.error(f"Erreur API send: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Erreur: {str(e)}'
                }), 500

        # API pour collecter ET envoyer en une fois
        @self.app.route('/api/collect-and-send', methods=['POST'])
        def api_collect_and_send():
            """API pour collecter et envoyer l'inventaire en une seule action"""
            try:
                if self.app_status['collection_in_progress'] or self.app_status['send_in_progress']:
                    return jsonify({
                        'success': False,
                        'message': 'Une opération est déjà en cours'
                    }), 400

                # Processus complet en arrière-plan
                def collect_and_send_background():
                    try:
                        # Phase 1: Collecte
                        self.app_status['collection_in_progress'] = True
                        self.app_logger.info("Démarrage collecte+envoi via web")

                        inventory_data = self.collector.collect_all(force_refresh=True)
                        self.app_status['last_collection'] = inventory_data
                        self.app_status['last_collection_time'] = datetime.now()
                        self.app_status['collection_in_progress'] = False

                        # Phase 2: Envoi
                        self.app_status['send_in_progress'] = True

                        success, message = self.sender.send_inventory_with_retry(
                            inventory_data,
                            max_retries=3
                        )

                        self.app_status['last_send_result'] = {
                            'success': success,
                            'message': message
                        }
                        self.app_status['last_send_time'] = datetime.now()

                        if success:
                            self.app_logger.info("Collecte+envoi terminé avec succès")
                        else:
                            self.app_logger.error(f"Collecte+envoi - envoi échoué: {message}")

                    except Exception as e:
                        self.app_logger.error(f"Erreur collecte+envoi: {e}")
                        self.app_status['last_send_result'] = {
                            'success': False,
                            'message': str(e)
                        }
                    finally:
                        self.app_status['collection_in_progress'] = False
                        self.app_status['send_in_progress'] = False

                # Lancer en thread
                thread = threading.Thread(target=collect_and_send_background, daemon=True)
                thread.start()

                return jsonify({
                    'success': True,
                    'message': 'Collecte et envoi démarrés'
                })

            except Exception as e:
                self.app_logger.error(f"Erreur API collect-and-send: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Erreur: {str(e)}'
                }), 500

        # API pour récupérer le statut en temps réel
        @self.app.route('/api/status')
        def api_status():
            """API pour récupérer le statut actuel de l'agent"""
            try:
                status_info = self._get_status_info()
                return jsonify(status_info)

            except Exception as e:
                self.app_logger.error(f"Erreur API status: {e}")
                return jsonify({
                    'error': str(e)
                }), 500

        # API pour tester la connexion serveur
        @self.app.route('/api/test-connection', methods=['POST'])
        def api_test_connection():
            """API pour tester la connexion au serveur"""
            try:
                # Récupérer les paramètres du test depuis la requête
                data = request.get_json()
                if data:
                    # Test avec des paramètres personnalisés
                    url = data.get('url')
                    auth_token = data.get('auth_token')
                    timeout = data.get('timeout', 30)

                    if url:
                        # Créer temporairement un sender avec ces paramètres
                        temp_config = self.config
                        temp_config.config.set('server', 'url', url)
                        if auth_token:
                            temp_config.config.set('server', 'auth_token', auth_token)
                        temp_config.config.set('server', 'timeout', str(timeout))

                        temp_sender = InventorySender(temp_config, self.logger)
                        success, message = temp_sender.test_connection()
                    else:
                        success, message = self.sender.test_connection()
                else:
                    success, message = self.sender.test_connection()

                return jsonify({
                    'success': success,
                    'message': message
                })

            except Exception as e:
                self.app_logger.error(f"Erreur API test-connection: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Erreur: {str(e)}'
                }), 500

        # API pour récupérer la configuration serveur
        @self.app.route('/api/config/server', methods=['GET'])
        def api_get_server_config():
            """API pour récupérer la configuration du serveur"""
            try:
                server_config = {
                    'url': self.config.get('server', 'url', fallback=''),
                    'auth_token': self.config.get('server', 'auth_token', fallback=''),
                    'timeout': self.config.getint('server', 'timeout', fallback=30),
                    'verify_ssl': self.config.getboolean('server', 'verify_ssl', fallback=True)
                }

                return jsonify(server_config)

            except Exception as e:
                self.app_logger.error(f"Erreur API get-server-config: {e}")
                return jsonify({
                    'error': str(e)
                }), 500

        # API pour sauvegarder la configuration serveur
        @self.app.route('/api/config/server', methods=['POST'])
        def api_save_server_config():
            """API pour sauvegarder la configuration du serveur"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': 'Données de configuration manquantes'
                    }), 400

                # Validation des données
                url = data.get('url', '').strip()
                auth_token = data.get('auth_token', '').strip()
                timeout = data.get('timeout', 30)

                if not url:
                    return jsonify({
                        'success': False,
                        'message': 'URL du serveur requise'
                    }), 400

                if not url.startswith(('http://', 'https://')):
                    return jsonify({
                        'success': False,
                        'message': 'URL invalide - doit commencer par http:// ou https://'
                    }), 400

                try:
                    timeout = int(timeout)
                    if timeout < 5 or timeout > 300:
                        raise ValueError()
                except (ValueError, TypeError):
                    return jsonify({
                        'success': False,
                        'message': 'Timeout doit être un nombre entre 5 et 300 secondes'
                    }), 400

                # Mettre à jour la configuration
                self.config.config.set('server', 'url', url)
                self.config.config.set('server', 'auth_token', auth_token)
                self.config.config.set('server', 'timeout', str(timeout))

                # Sauvegarder la configuration
                self.config.save()

                # Recréer le sender avec la nouvelle configuration
                self.sender = InventorySender(self.config, self.logger)

                self.app_logger.info(f"Configuration serveur mise à jour: {url}")

                return jsonify({
                    'success': True,
                    'message': 'Configuration sauvegardée avec succès'
                })

            except Exception as e:
                self.app_logger.error(f"Erreur API save-server-config: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Erreur: {str(e)}'
                }), 500


    def _get_status_info(self) -> dict:
        """
        Récupère les informations de statut complètes

        Returns:
            dict: Informations de statut
        """
        try:
            status = {
                # État des opérations
                'collection_in_progress': self.app_status['collection_in_progress'],
                'send_in_progress': self.app_status['send_in_progress'],

                # Dernière collecte
                'last_collection_time': self.app_status['last_collection_time'].isoformat() if self.app_status['last_collection_time'] else None,
                'has_collection_data': self.app_status['last_collection'] is not None,

                # Dernière envoi
                'last_send_time': self.app_status['last_send_time'].isoformat() if self.app_status['last_send_time'] else None,
                'last_send_success': self.app_status['last_send_result']['success'] if self.app_status['last_send_result'] else None,
                'last_send_message': self.app_status['last_send_result']['message'] if self.app_status['last_send_result'] else None,

                # Statistiques du collecteur
                'collector_stats': self.collector.get_collection_stats(),

                # Statistiques du sender
                'sender_stats': self.sender.get_stats(),

                # Configuration serveur (sans token)
                'server_url': self.config.get('server', 'url'),
                'server_configured': bool(self.config.get('server', 'auth_token')),

                # Informations système de base
                'hostname': self.collector._get_hostname(),
                'platform': sys.platform,

                # Timestamp du statut
                'status_timestamp': datetime.now().isoformat()
            }

            return status

        except Exception as e:
            self.app_logger.error(f"Erreur récupération statut: {e}")
            return {
                'error': str(e),
                'status_timestamp': datetime.now().isoformat()
            }

    def _get_recent_logs(self, max_lines=100) -> list:
        """
        Récupère les logs récents

        Args:
            max_lines: Nombre maximum de lignes à retourner

        Returns:
            list: Entrées de log récentes
        """
        logs = []

        try:
            log_file = self.config.get('logging', 'log_file')

            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Prendre les dernières lignes
                recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

                for line in recent_lines:
                    line = line.strip()
                    if line:
                        # Parser basique du format de log
                        parts = line.split(' - ', 4)
                        if len(parts) >= 4:
                            log_entry = {
                                'timestamp': parts[0],
                                'logger': parts[1],
                                'level': parts[2],
                                'message': ' - '.join(parts[3:])
                            }
                        else:
                            log_entry = {
                                'timestamp': '',
                                'logger': '',
                                'level': 'INFO',
                                'message': line
                            }

                        logs.append(log_entry)

        except Exception as e:
            self.app_logger.error(f"Erreur lecture logs: {e}")
            logs.append({
                'timestamp': datetime.now().isoformat(),
                'logger': 'WebApp',
                'level': 'ERROR',
                'message': f'Erreur lecture fichier log: {e}'
            })

        return logs

    def run(self, host='127.0.0.1', port=8080, debug=False):
        """
        Lance l'application Flask

        Args:
            host: Adresse d'écoute
            port: Port d'écoute
            debug: Mode debug Flask
        """
        try:
            # Utiliser la configuration pour host et port si disponible
            web_config = self.config.get_web_config()
            host = web_config.get('host', host)
            port = web_config.get('port', port)

            self.app_logger.info(f"Démarrage interface web sur http://{host}:{port}")

            self.app.run(
                host=host,
                port=port,
                debug=debug,
                threaded=True,  # Permet les requêtes concurrentes
                use_reloader=False  # Évite les problèmes avec les threads
            )

        except Exception as e:
            self.app_logger.error(f"Erreur démarrage interface web: {e}")
            raise

    def stop(self):
        """
        Arrête l'application web proprement
        """
        self.app_logger.info("Arrêt de l'interface web")
        # Flask n'a pas de méthode stop() native
        # L'arrêt se fait généralement par interruption du processus


def create_app(config_path=None):
    """
    Factory function pour créer l'application Flask

    Args:
        config_path: Chemin vers le fichier de configuration

    Returns:
        InventoryWebApp: Instance de l'application
    """
    return InventoryWebApp(config_path)