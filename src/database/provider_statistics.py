"""
Provider Statistics Tracker for CyberScout AI.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from src.database.connection import DatabaseManager


class ProviderStatisticsTracker:
    """
    Updates provider_statistics table metrics.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def update_provider_stats(self, provider_name: str, score: int) -> None:
        """Upserts provider activity record."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO provider_statistics (provider_name, total_opportunities, active_opportunities, average_score, last_seen)
            VALUES (?, 1, 1, ?, ?)
            ON CONFLICT(provider_name) DO UPDATE SET
                total_opportunities = total_opportunities + 1,
                active_opportunities = active_opportunities + 1,
                average_score = (average_score + excluded.average_score) / 2.0,
                last_seen = excluded.last_seen;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (provider_name, float(score), now))
        except Exception:
            pass
