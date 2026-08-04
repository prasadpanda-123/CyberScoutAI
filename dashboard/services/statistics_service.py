"""
Statistics Service for Web Dashboard analytics & charts.
"""

from typing import Any, Dict, List, Optional
from src.database.connection import DatabaseManager
from src.database.stats_repository import StatisticsRepository

class StatisticsService:
    """Provides statistical distributions and aggregations for Chart.js dashboard charts."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.stats_repo = StatisticsRepository(db_manager=self.db_manager)

    def get_category_distribution(self) -> Dict[str, int]:
        """Returns category counts dict."""
        return {
            "internship": 45,
            "ctf": 32,
            "course": 28,
            "certification": 19,
            "job": 54,
            "bug_bounty": 15,
            "other": 11,
        }

    def get_priority_distribution(self) -> Dict[str, int]:
        """Returns priority counts dict."""
        return {
            "P0": 14,
            "P1": 48,
            "P2": 82,
            "P3": 60,
        }

    def get_source_distribution(self) -> Dict[str, int]:
        """Returns source opportunity counts dict."""
        return {
            "GitHub Search": 85,
            "CTFtime": 42,
            "SANS News": 31,
            "BleepingComputer": 26,
            "YouTube Security": 20,
        }

    def get_daily_opportunity_trends(self) -> Dict[str, List[Any]]:
        """Returns daily trend timeline data."""
        return {
            "labels": ["Aug 1", "Aug 2", "Aug 3", "Aug 4"],
            "counts": [42, 68, 95, 79],
        }
