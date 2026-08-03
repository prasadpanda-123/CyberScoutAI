"""
Statistics Manager for CyberScout AI.
"""

from typing import Any, Dict, Optional

from src.database.connection import DatabaseManager
from src.database.stats_repository import StatisticsRepository


class StatisticsManager:
    """
    Manages daily application statistics records.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.repo = StatisticsRepository(db_manager=self.db_manager)

    def get_latest_statistics(self) -> Dict[str, Any]:
        """Retrieves most recent statistics record."""
        stats = self.repo.get_latest()
        if stats:
            return stats.to_dict()
        return {}
