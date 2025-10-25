"""
Module de planification pour l'agent d'inventaire

Ce module gère :
- La planification des collectes d'inventaire périodiques
- L'exécution des tâches en arrière-plan
- La gestion des intervalles de temps
- Le démarrage et arrêt du scheduler
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional
import schedule
from enum import Enum


class FrequencyType(Enum):
    """Énumération des types de fréquence supportés"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    HOURLY = "hourly"  # Pour les tests


class InventoryScheduler:
    """
    Gestionnaire de planification pour l'agent d'inventaire

    Cette classe utilise le module 'schedule' pour planifier l'exécution
    automatique des collectes d'inventaire selon la fréquence configurée.
    """

    def __init__(self, config, logger, inventory_callback: Callable[[], None]):
        """
        Initialise le scheduler

        Args:
            config: Instance de AgentConfig
            logger: Instance de AgentLogger
            inventory_callback: Fonction à appeler pour déclencher une collecte
        """
        self.config = config
        self.logger = logger.get_logger()
        self.inventory_callback = inventory_callback

        # État du scheduler
        self.is_running = False
        self.scheduler_thread = None
        self.stop_event = threading.Event()

        # Planification
        self.frequency = None
        self.next_run = None

        self._setup_schedule()

        self.logger.info("InventoryScheduler initialisé")

    def _setup_schedule(self):
        """
        Configure la planification basée sur la configuration
        """
        # Récupérer la fréquence depuis la configuration
        frequency_str = self.config.get('agent', 'reporting_frequency', 'daily')

        try:
            self.frequency = FrequencyType(frequency_str)
        except ValueError:
            self.logger.warning(f"Fréquence inconnue '{frequency_str}', utilisation de 'daily'")
            self.frequency = FrequencyType.DAILY

        # Effacer les tâches existantes
        schedule.clear()

        # Configurer la nouvelle planification
        if self.frequency == FrequencyType.HOURLY:
            # Pour les tests - chaque heure
            schedule.every().hour.do(self._scheduled_inventory)
            self.logger.info("Planification configurée: toutes les heures")

        elif self.frequency == FrequencyType.DAILY:
            # Chaque jour à 02:00 du matin (évite les heures de pointe)
            schedule.every().day.at("02:00").do(self._scheduled_inventory)
            self.logger.info("Planification configurée: quotidienne à 02:00")

        elif self.frequency == FrequencyType.WEEKLY:
            # Chaque dimanche à 02:00
            schedule.every().sunday.at("02:00").do(self._scheduled_inventory)
            self.logger.info("Planification configurée: hebdomadaire le dimanche à 02:00")

        elif self.frequency == FrequencyType.MONTHLY:
            # Le premier de chaque mois à 02:00
            # Note: schedule ne supporte pas directement "monthly",
            # on utilise une vérification personnalisée
            schedule.every().day.at("02:00").do(self._check_monthly_schedule)
            self.logger.info("Planification configurée: mensuelle le 1er du mois à 02:00")

        # Calculer la prochaine exécution
        self._update_next_run()

    def _scheduled_inventory(self):
        """
        Méthode appelée par le scheduler pour déclencher une collecte

        Cette méthode est appelée automatiquement selon la planification
        et lance la collecte d'inventaire.
        """
        self.logger.info("=== Collecte d'inventaire planifiée déclenchée ===")

        try:
            # Appeler la fonction de collecte
            self.inventory_callback()

            self.logger.info("Collecte d'inventaire planifiée terminée avec succès")

        except Exception as e:
            self.logger.exception("Erreur lors de la collecte planifiée")

        finally:
            # Mettre à jour la prochaine exécution
            self._update_next_run()

    def _check_monthly_schedule(self):
        """
        Vérification spéciale pour la planification mensuelle

        Exécute la collecte seulement si on est le premier jour du mois.
        """
        today = datetime.now()

        if today.day == 1:  # Premier jour du mois
            self.logger.info("Première jour du mois détecté - collecte mensuelle")
            self._scheduled_inventory()
        else:
            # Pas le premier jour, ne rien faire
            pass

    def _update_next_run(self):
        """
        Met à jour le timestamp de la prochaine exécution
        """
        jobs = schedule.get_jobs()
        if jobs:
            # Prendre la prochaine exécution de la première tâche
            next_job = min(jobs, key=lambda job: job.next_run)
            self.next_run = next_job.next_run
            self.logger.debug(f"Prochaine collecte planifiée: {self.next_run}")

    def start(self):
        """
        Démarre le scheduler en arrière-plan

        Lance un thread séparé qui exécute la boucle de planification.
        """
        if self.is_running:
            self.logger.warning("Scheduler déjà en cours d'exécution")
            return

        self.logger.info("Démarrage du scheduler...")

        self.is_running = True
        self.stop_event.clear()

        # Créer et démarrer le thread du scheduler
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="InventoryScheduler",
            daemon=True
        )
        self.scheduler_thread.start()

        self.logger.info(f"Scheduler démarré (fréquence: {self.frequency.value})")

        if self.next_run:
            self.logger.info(f"Prochaine collecte: {self.next_run}")

    def stop(self):
        """
        Arrête le scheduler

        Stoppe proprement le thread de planification.
        """
        if not self.is_running:
            self.logger.warning("Scheduler pas en cours d'exécution")
            return

        self.logger.info("Arrêt du scheduler...")

        self.is_running = False
        self.stop_event.set()

        # Attendre que le thread se termine
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)

        self.logger.info("Scheduler arrêté")

    def _scheduler_loop(self):
        """
        Boucle principale du scheduler

        Cette méthode tourne en arrière-plan et vérifie périodiquement
        s'il faut exécuter des tâches planifiées.
        """
        self.logger.debug("Boucle du scheduler démarrée")

        while not self.stop_event.is_set():
            try:
                # Vérifier et exécuter les tâches planifiées
                schedule.run_pending()

                # Attendre 60 secondes avant la prochaine vérification
                # (ou jusqu'à ce qu'on demande l'arrêt)
                self.stop_event.wait(timeout=60)

            except Exception as e:
                self.logger.exception("Erreur dans la boucle du scheduler")
                # Attendre un peu avant de continuer en cas d'erreur
                self.stop_event.wait(timeout=10)

        self.logger.debug("Boucle du scheduler terminée")

    def force_run(self):
        """
        Force l'exécution immédiate d'une collecte d'inventaire

        Cette méthode permet de déclencher manuellement une collecte
        sans attendre la prochaine exécution planifiée.
        """
        self.logger.info("Collecte d'inventaire forcée demandée")

        try:
            self.inventory_callback()
            self.logger.info("Collecte d'inventaire forcée terminée")

        except Exception as e:
            self.logger.exception("Erreur lors de la collecte forcée")

    def get_status(self) -> dict:
        """
        Retourne le statut actuel du scheduler

        Returns:
            dict: Informations sur l'état du scheduler
        """
        return {
            'is_running': self.is_running,
            'frequency': self.frequency.value if self.frequency else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'next_run_in': str(self.next_run - datetime.now()) if self.next_run else None,
            'scheduled_jobs_count': len(schedule.get_jobs())
        }

    def update_frequency(self, new_frequency: str):
        """
        Met à jour la fréquence de planification

        Args:
            new_frequency: Nouvelle fréquence (daily, weekly, monthly, hourly)
        """
        self.logger.info(f"Mise à jour de la fréquence: {new_frequency}")

        # Mettre à jour la configuration
        self.config.set('agent', 'reporting_frequency', new_frequency)

        # Reconfigurer la planification
        self._setup_schedule()

        self.logger.info(f"Fréquence mise à jour vers: {new_frequency}")

        if self.next_run:
            self.logger.info(f"Nouvelle prochaine collecte: {self.next_run}")

    def get_next_runs(self, count: int = 5) -> list:
        """
        Retourne les prochaines exécutions planifiées

        Args:
            count: Nombre d'exécutions à retourner

        Returns:
            list: Liste des prochaines dates d'exécution
        """
        jobs = schedule.get_jobs()
        if not jobs:
            return []

        next_runs = []
        current_time = datetime.now()

        # Simuler les prochaines exécutions
        for job in jobs:
            next_run = job.next_run
            for i in range(count):
                if next_run > current_time:
                    next_runs.append(next_run)

                # Calculer la prochaine occurrence (approximation)
                if self.frequency == FrequencyType.HOURLY:
                    next_run += timedelta(hours=1)
                elif self.frequency == FrequencyType.DAILY:
                    next_run += timedelta(days=1)
                elif self.frequency == FrequencyType.WEEKLY:
                    next_run += timedelta(weeks=1)
                elif self.frequency == FrequencyType.MONTHLY:
                    # Approximation pour mensuel
                    next_run += timedelta(days=30)

        return sorted(next_runs)[:count]