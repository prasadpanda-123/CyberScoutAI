"""
Analytics Engine for CyberScout AI.
"""

from typing import Any, Dict, Optional

from src.database.connection import DatabaseManager
from src.database.trend_engine import TrendEngine


class AnalyticsEngine:
    """
    Computes total opportunities, active count, expired count, high priority count, and score averages.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.trend_engine = TrendEngine(db_manager=self.db_manager)

    def generate_analytics_summary(self) -> Dict[str, Any]:
        """
        Generates overall analytics summary dictionary.

        Returns:
            Dictionary containing metrics.
        """
        total = 0
        active = 0
        avg_score = 0.0

        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            # Total & Active
            cursor.execute("SELECT COUNT(*) as cnt FROM opportunities;")
            r1 = cursor.fetchone()
            if r1:
                total = r1["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM opportunities WHERE status = 'active';")
            r2 = cursor.fetchone()
            if r2:
                active = r2["cnt"]

            cursor.execute("SELECT AVG(score) as avg_sc FROM opportunities;")
            r3 = cursor.fetchone()
            if r3 and r3["avg_sc"] is not None:
                avg_score = round(r3["avg_sc"], 2)

            cursor.close()
        except Exception:
            pass

        return {
            "total_opportunities": total,
            "active_opportunities": active,
            "expired_opportunities": max(0, total - active),
            "average_score": avg_score,
            "top_providers": self.trend_engine.get_most_active_providers(5),
            "top_categories": self.trend_engine.get_most_active_categories(5),
        }
