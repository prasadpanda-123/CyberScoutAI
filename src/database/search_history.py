"""
Search History Tracker for CyberScout AI.
"""

from typing import Optional

from src.database.connection import DatabaseManager
from src.database.history_repository import SearchHistoryRepository
from src.models.search_models import SearchQuery


class SearchHistoryTracker:
    """
    Logs executed SearchQuery records into search_history table.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.repo = SearchHistoryRepository(db_manager=self.db_manager)

    def log_query(self, query: SearchQuery) -> None:
        """Logs a search query execution."""
        try:
            self.repo.save(query)
        except Exception:
            pass
