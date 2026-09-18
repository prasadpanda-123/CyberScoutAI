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
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT LOWER(category) as cat, COUNT(*) as cnt 
                FROM "Opportunities" 
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
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return {}
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_priority_distribution(self) -> Dict[str, int]:
        """Returns 100% real priority distribution counts derived from score ranges."""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    CASE 
                        WHEN score >= 80 THEN 'P0'
                        WHEN score >= 60 THEN 'P1'
                        WHEN score >= 40 THEN 'P2'
                        ELSE 'P3'
                    END as prio,
                    COUNT(*) as cnt 
                FROM "Opportunities" 
                WHERE is_rejected IS NOT TRUE 
                GROUP BY 
                    CASE 
                        WHEN score >= 80 THEN 'P0'
                        WHEN score >= 60 THEN 'P1'
                        WHEN score >= 40 THEN 'P2'
                        ELSE 'P3'
                    END
                ORDER BY prio
                """
            )
            rows = cursor.fetchall()
            return {str(r[0]): int(r[1]) for r in rows if r[0]}
        except Exception as e:
            logger.error(f"Error fetching priority distribution: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return {}
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_source_distribution(self) -> Dict[str, int]:
        """Returns 100% real opportunity counts per source provider from PostgreSQL database."""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(s.name, o.provider, o.source_id, 'Direct Discovery') as src, COUNT(*) as cnt 
                FROM "Opportunities" o
                LEFT JOIN "Sources" s ON o.source_id = s.id
                WHERE o.is_rejected IS NOT TRUE 
                GROUP BY COALESCE(s.name, o.provider, o.source_id, 'Direct Discovery')
                ORDER BY cnt DESC 
                LIMIT 8
                """
            )
            rows = cursor.fetchall()
            return {str(r[0]): int(r[1]) for r in rows if r[0]}
        except Exception as e:
            logger.error(f"Error fetching source distribution: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return {}
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_daily_opportunity_trends(self) -> Dict[str, List[Any]]:
        """Returns 100% real timeline data aggregated by discovered date from PostgreSQL database."""
        conn = None
        cursor = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT discovered_date, COUNT(*) as cnt 
                FROM "Opportunities" 
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
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return {"labels": [], "counts": []}
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
