"""
Trend Engine for CyberScout AI.
"""

from typing import Any, Dict, List, Optional

from src.database.connection import DatabaseManager


class TrendEngine:
    """
    Computes most active providers, categories, common skills, and growth rates.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def get_most_active_providers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns top active providers."""
        sql = """
            SELECT provider, COUNT(*) as count
            FROM opportunities
            WHERE provider IS NOT NULL
            GROUP BY provider
            ORDER BY count DESC
            LIMIT ?;
        """
        results = []
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            cursor.close()
            for r in rows:
                results.append({"provider": r["provider"], "count": r["count"]})
        except Exception:
            pass
        return results

    def get_most_active_categories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns top active categories."""
        sql = """
            SELECT category, COUNT(*) as count
            FROM opportunities
            GROUP BY category
            ORDER BY count DESC
            LIMIT ?;
        """
        results = []
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            cursor.close()
            for r in rows:
                results.append({"category": r["category"], "count": r["count"]})
        except Exception:
            pass
        return results
