"""
Statistics Service for Web Dashboard analytics & telemetry.
Calculates 100% real dynamic aggregations from PostgreSQL database.
"""

from typing import Any, Dict, List, Optional
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.stats_repository import StatisticsRepository

logger = get_logger(__name__)


class StatisticsService:
    """Provides dynamic statistical distributions and aggregations from the database."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.stats_repo = StatisticsRepository(db_manager=self.db_manager)

    def get_category_distribution(self) -> Dict[str, int]:
        """Returns 100% real category opportunity counts from PostgreSQL database."""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT LOWER(category) as cat, COUNT(*) as cnt 
                FROM Opportunities 
                WHERE is_rejected IS NOT TRUE AND category IS NOT NULL 
                GROUP BY LOWER(category)
                """
            )
            rows = cursor.fetchall()
            cat_map: Dict[str, int] = {}
            for r in rows:
                if r[0]:
                    key = str(r[0]).strip().lower().replace("-", "_").replace(" ", "_")
                    cat_map[key] = int(r[1])
            return cat_map
        except Exception as e:
            logger.error(f"Error fetching category distribution from DB: {e}")
            return {}

    def get_priority_distribution(self) -> Dict[str, int]:
        """Returns 100% real priority distribution counts from PostgreSQL database."""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT UPPER(priority) as prio, COUNT(*) as cnt 
                FROM Opportunities 
                WHERE is_rejected IS NOT TRUE AND priority IS NOT NULL 
                GROUP BY UPPER(priority)
                ORDER BY prio
                """
            )
            rows = cursor.fetchall()
            return {str(r[0]): int(r[1]) for r in rows if r[0]}
        except Exception as e:
            logger.error(f"Error fetching priority distribution: {e}")
            return {}

    def get_source_distribution(self) -> Dict[str, int]:
        """Returns 100% real opportunity counts per source provider from PostgreSQL database."""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(source, 'Direct Discovery') as src, COUNT(*) as cnt 
                FROM Opportunities 
                WHERE is_rejected IS NOT TRUE 
                GROUP BY source 
                ORDER BY cnt DESC 
                LIMIT 8
                """
            )
            rows = cursor.fetchall()
            return {str(r[0]): int(r[1]) for r in rows if r[0]}
        except Exception as e:
            logger.error(f"Error fetching source distribution: {e}")
            return {}

    def get_daily_opportunity_trends(self) -> Dict[str, List[Any]]:
        """Returns 100% real timeline data aggregated by discovered date from PostgreSQL database."""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT discovered_date, COUNT(*) as cnt 
                FROM Opportunities 
                WHERE is_rejected IS NOT TRUE AND discovered_date IS NOT NULL 
                GROUP BY discovered_date 
                ORDER BY discovered_date DESC 
                LIMIT 7
                """
            )
            rows = cursor.fetchall()
            rows.reverse()
            labels = [str(r[0]) for r in rows]
            counts = [int(r[1]) for r in rows]
            return {"labels": labels, "counts": counts}
        except Exception as e:
            logger.error(f"Error fetching daily trends from DB: {e}")
            return {"labels": [], "counts": []}

