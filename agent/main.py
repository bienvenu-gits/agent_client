"""
Point d'entrée principal de l'Watchman Agent Client

Ce module orchestre tous les composants de l'agent et peut être exécuté
de différentes manières selon les besoins :
- En mode service/daemon système
- En mode interface web standalone
- En mode collecte unique
- En mode développement
"""

import os
import sys
import time
import signal
import argparse
import threading
from pathlib import Path

from agent.services.service_manager import ServiceManager

# Ajouter le chemin racine pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core.config import AgentConfig, create_default_config
from agent.core.logger import AgentLogger
from agent.core.collector import InventoryCollector
from agent.core.sender import InventorySender
from agent.core.scheduler import InventoryScheduler
from agent.web.app import InventoryWebApp


class WatchmanAgentClient:
    """
    Watchman Agent Client principal

    Cette classe orchestre tous les composants de l'agent d'inventaire
    et gère les différents modes de fonctionnement.
    """

    def __init__(self, config_path=None):
        """
        Initialise l'agent d'inventaire

        Args:
            config_path: Chemin vers le fichier de configuration
        """
        # Configuration
        self.config = AgentConfig(config_path)

        # Logger
        self.logger = AgentLogger(self.config)
        self.app_logger = self.logger.get_logger()

        # Composants principaux
        self.collector = InventoryCollector(self.config, self.logger)
        self.sender = InventorySender(self.config, self.logger)
        self.scheduler = None
        self.web_app = None

        # État de l'agent
        self.running = False
        self.shutdown_event = threading.Event()

        self.app_logger.info("Watchman Agent Client initialisé")

    def start_scheduler(self):
        """
        Démarre le planificateur de collectes automatiques
        """
        if self.scheduler:
            self.app_logger.warning("Le planificateur est déjà démarré")
            return

        self.app_logger.info("Démarrage du planificateur d'inventaire")

        # Créer le planificateur avec callback vers collect_and_send
        self.scheduler = InventoryScheduler(
            self.config,
            self.logger,
            self.collect_and_send
        )

        # Démarrer le planificateur
        self.scheduler.start()

        self.app_logger.info("Planificateur démarré avec succès")

    def stop_scheduler(self):
        """
        Arrête le planificateur
        """
        if self.scheduler:
            self.app_logger.info("Arrêt du planificateur")
            self.scheduler.stop()
            self.scheduler = None

    def start_web_interface(self):
        """
        Démarre l'interface web
        """
        web_config = self.config.get_web_config()

        if not web_config['enabled']:
            self.app_logger.info("Interface web désactivée dans la configuration")
            return

        self.app_logger.info("Démarrage de l'interface web...")

        try:
            self.web_app = InventoryWebApp(self.config.config_file)

            # Démarrer dans un thread séparé (NON daemon pour service Windows)
            web_thread = threading.Thread(
                target=self._run_web_app,
                args=(web_config['host'], web_config['port']),
                daemon=False,  # Non daemon pour que le service ne termine pas
                name="WebInterface"
            )
            web_thread.start()

            # Attendre un peu pour vérifier le démarrage
            time.sleep(1)

            self.app_logger.info(f"Thread interface web démarré - http://{web_config['host']}:{web_config['port']}")

        except Exception as e:
            self.app_logger.error(f"Erreur démarrage interface web: {e}")
            self.app_logger.exception("Stack trace complète:")

    def _run_web_app(self, host, port):
        """
        Lance l'application web Flask

        Args:
            host: Adresse d'écoute
            port: Port d'écoute
        """
        try:
            self.app_logger.info(f"Tentative de bind Flask sur {host}:{port}")

            # Flask run pour service Windows
            self.web_app.run(
                host=host,
                port=port,
                debug=False
            )

        except Exception as e:
            self.app_logger.error(f"Erreur dans l'interface web: {e}")
            self.app_logger.exception("Stack trace Flask:")

    def collect_and_send(self):
        """
        Effectue une collecte complète et envoie les données

        Cette méthode est appelée par le planificateur ou manuellement.
        """
        try:
            self.app_logger.info("=== Début de collecte et envoi automatique ===")

            # Phase 1: Collecte
            self.app_logger.info("Phase 1: Collecte des données d'inventaire")
            inventory_data = self.collector.collect_all(force_refresh=True)

            # Phase 2: Envoi
            self.app_logger.info("Phase 2: Envoi des données au serveur")
            success, message = self.sender.send_inventory_with_retry(
                inventory_data,
                max_retries=3,
                retry_delay=10
            )

            if success:
                self.app_logger.info(f"Collecte et envoi terminés avec succès: {message}")
            else:
                self.app_logger.error(f"Erreur lors de l'envoi: {message}")

            self.app_logger.info("=== Fin de collecte et envoi automatique ===")

        except Exception as e:
            self.app_logger.exception("Erreur lors de la collecte et envoi")

    def collect_only(self):
        """
        Effectue seulement une collecte d'inventaire

        Returns:
            dict: Données d'inventaire collectées
        """
        try:
            self.app_logger.info("=== Collecte unique d'inventaire ===")
            inventory_data = self.collector.collect_all(force_refresh=True)
            self.app_logger.info("Collecte terminée avec succès")
            return inventory_data

        except Exception as e:
            self.app_logger.exception("Erreur lors de la collecte")
            return None

    def send_only(self, inventory_data):
        """
        Effectue seulement l'envoi de données existantes

        Args:
            inventory_data: Données d'inventaire à envoyer

        Returns:
            tuple: (success, message)
        """
        try:
            self.app_logger.info("=== Envoi unique d'inventaire ===")
            success, message = self.sender.send_inventory_with_retry(
                inventory_data,
                max_retries=3
            )

            if success:
                self.app_logger.info(f"Envoi terminé avec succès: {message}")
            else:
                self.app_logger.error(f"Erreur lors de l'envoi: {message}")

            return success, message

        except Exception as e:
            self.app_logger.exception("Erreur lors de l'envoi")
            return False, str(e)

    def run_service_mode(self):
        """
        Lance l'agent en mode service/daemon

        Ce mode démarre tous les composants :
        - Planificateur de collectes automatiques
        - Interface web (si activée)
        - Gestionnaire de signaux pour l'arrêt propre
        """
        self.app_logger.info("Démarrage de l'Watchman Agent Client en mode service")

        try:
            # Configurer les gestionnaires de signaux
            self._setup_signal_handlers()

            # Démarrer les composants
            self.start_scheduler()
            self.start_web_interface()

            # Marquer comme en cours d'exécution
            self.running = True

            self.app_logger.info("✅ Watchman Agent Client démarré avec succès")
            self.app_logger.info("Appuyez sur Ctrl+C pour arrêter l'agent")

            # Boucle principale - attendre l'arrêt
            while self.running and not self.shutdown_event.is_set():
                self.shutdown_event.wait(timeout=1.0)

        except KeyboardInterrupt:
            self.app_logger.info("Interruption clavier détectée")
        except Exception as e:
            self.app_logger.error(f"Erreur en mode service: {e}")
        finally:
            self.shutdown()

    def run_web_only_mode(self):
        """
        Lance seulement l'interface web (mode développement/debug)
        """
        self.app_logger.info("Démarrage en mode interface web seulement")

        try:
            web_config = self.config.get_web_config()

            # Forcer l'activation de l'interface web
            if not web_config['enabled']:
                self.app_logger.warning("Interface web forcée en mode développement")
                web_config['enabled'] = True

            self.web_app = InventoryWebApp(self.config.config_file)
            self.web_app.run(
                host=web_config['host'],
                port=web_config['port'],
                debug=True
            )

        except KeyboardInterrupt:
            self.app_logger.info("Interface web arrêtée")
        except Exception as e:
            self.app_logger.error(f"Erreur interface web: {e}")

    def _setup_signal_handlers(self):
        """
        Configure les gestionnaires de signaux pour l'arrêt propre
        """
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.app_logger.info(f"Signal {signal_name} reçu - Arrêt en cours...")
            self.shutdown()

        # Gestionnaires de signaux Unix/Linux
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler)

        # Windows
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)

    def shutdown(self):
        """
        Arrête proprement tous les composants de l'agent
        """
        if not self.running:
            return

        self.app_logger.info("🛑 Arrêt de l'Watchman Agent Client...")

        self.running = False
        self.shutdown_event.set()

        # Arrêter les composants
        if self.scheduler:
            self.stop_scheduler()

        if self.web_app:
            self.app_logger.info("Arrêt de l'interface web")
            # Flask n'a pas de méthode stop() native

        self.app_logger.info("✅ Watchman Agent Client arrêté proprement")

    def get_status(self):
        """
        Retourne le statut actuel de l'agent

        Returns:
            dict: Statut de tous les composants
        """
        status = {
            'running': self.running,
            'components': {
                'scheduler': {
                    'active': self.scheduler is not None and self.scheduler.is_running,
                    'next_run': None
                },
                'web_interface': {
                    'active': self.web_app is not None,
                    'config': self.config.get_web_config()
                },
                'collector': {
                    'stats': self.collector.get_collection_stats()
                },
                'sender': {
                    'stats': self.sender.get_stats()
                }
            },
            'config': {
                'file': self.config.config_file,
                'valid': self.config.validate()
            }
        }

        # Ajouter les infos du scheduler si actif
        if self.scheduler:
            scheduler_status = self.scheduler.get_status()
            status['components']['scheduler'].update(scheduler_status)

        return status


def main():
    """
    Point d'entrée principal avec gestion des arguments de ligne de commande
    """
    parser = argparse.ArgumentParser(
        description='Agent d\'Inventaire - Collecte automatisée d\'informations système'
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Chemin vers le fichier de configuration'
    )

    parser.add_argument(
        '--mode', '-m',
        choices=['service', 'web', 'collect', 'send', 'test', 'install_service', 'uninstall_service', 'service_status'],
        default='service',
        help='Mode de fonctionnement de l\'agent'
    )

    parser.add_argument(
        '--create-config',
        action='store_true',
        help='Crée un fichier de configuration par défaut'
    )

    parser.add_argument(
        '--validate-config',
        action='store_true',
        help='Valide la configuration actuelle'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Affiche le statut de l\'agent'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Fichier de sortie pour les données d\'inventaire (mode collect)'
    )

    args = parser.parse_args()

    # Créer une configuration par défaut
    if args.create_config:
        config_path = args.config or input("Chemin du fichier de configuration à créer: ")
        try:
            config = create_default_config(config_path)
            print(f"✅ Configuration par défaut créée: {config_path}")
            return 0
        except Exception as e:
            print(f"❌ Erreur création configuration: {e}")
            return 1

    # Créer l'agent
    try:
        agent = WatchmanAgentClient(args.config)
    except Exception as e:
        print(f"❌ Erreur initialisation agent: {e}")
        return 1

    # Valider la configuration
    if args.validate_config:
        if agent.config.validate():
            print("✅ Configuration valide")
            return 0
        else:
            print("❌ Configuration invalide")
            return 1

    # Afficher le statut
    if args.status:
        status = agent.get_status()
        print(f"Agent Status: {'🟢 Running' if status['running'] else '🔴 Stopped'}")
        print(f"Config File: {status['config']['file']}")
        print(f"Config Valid: {'✅' if status['config']['valid'] else '❌'}")

        for component, info in status['components'].items():
            state = '🟢 Active' if info.get('active') else '🔴 Inactive'
            print(f"{component.title()}: {state}")

        return 0

    # Modes de fonctionnement
    try:
        service_manager = ServiceManager("watchman-agent-client")
        if args.mode=='install_service':
            service_manager.install_service()
            return 0
        elif args.mode == 'uninstall_service':
            service_manager.uninstall_service()
            return 0
            
        elif args.mode == 'service_status':
            status = service_manager.get_service_status()
            print(f"🔍 État du service '{service_manager.service_name}':")
            print(f"   Installé: {'✅' if status['installed'] else '❌'}")
            print(f"   En cours: {'✅' if status['running'] else '❌'}")
            if status['output']:
                print(f"   Détails: {status['output']}")
            return 0
            
        elif args.mode == 'service':
            agent.run_service_mode()

        elif args.mode == 'web':
            agent.run_web_only_mode()

        elif args.mode == 'collect':
            data = agent.collect_only()
            if data and args.output:
                import json
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"✅ Données sauvegardées dans: {args.output}")
            elif data:
                print("✅ Collecte terminée avec succès")
            else:
                print("❌ Erreur lors de la collecte")
                return 1

        elif args.mode == 'send':
            # Pour le mode send, on a besoin de données existantes
            if args.output and os.path.exists(args.output):
                import json
                with open(args.output, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                success, message = agent.send_only(data)
                if success:
                    print(f"✅ Envoi réussi: {message}")
                else:
                    print(f"❌ Erreur envoi: {message}")
                    return 1
            else:
                print("❌ Aucune donnée à envoyer. Utilisez --output pour spécifier le fichier.")
                return 1

        elif args.mode == 'test':
            print("🧪 Test de l'agent d'inventaire")

            # Test de collecte
            print("1. Test de collecte...")
            data = agent.collect_only()
            if data:
                print("   ✅ Collecte OK")
            else:
                print("   ❌ Collecte échouée")
                return 1

            # Test de connexion serveur
            print("2. Test de connexion serveur...")
            success, message = agent.sender.test_connection()
            if success:
                print(f"   ✅ Connexion OK: {message}")
            else:
                print(f"   ⚠️  Connexion: {message}")

            print("✅ Tests terminés")

        return 0

    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur")
        return 0
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)