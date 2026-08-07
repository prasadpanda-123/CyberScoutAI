"""
Notifier Delivery History Tracker for CyberScout AI.
"""

from typing import Optional

from src.database.connection import DatabaseManager
from src.database.history_repository import EmailHistoryRepository


class HistoryTracker:
    """
    Logs email delivery outcomes into PostgreSQL database EmailHistory table.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.repo = EmailHistoryRepository(db_manager=self.db_manager)

    def log_delivery(self, opportunity_id: str, email_run_id: str) -> None:
        """
        Records an emailed opportunity link entry.
        """
        try:
            self.repo.record_emailed_opportunity(opportunity_id, email_run_id=email_run_id)
        except Exception:
            pass

    def log_deliveries_batch(self, opportunity_ids: list[str], email_run_id: str) -> None:
        """
        Records batch of emailed opportunity entries in a single transaction.
        """
        try:
            self.repo.record_emailed_opportunities_batch(opportunity_ids, email_run_id=email_run_id)
        except Exception:
            pass
