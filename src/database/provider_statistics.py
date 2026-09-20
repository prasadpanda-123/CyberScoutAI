"""
Provider Statistics Tracker & Manager for CyberScout AI.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.database.connection import DatabaseManager
from src.core.logging import get_logger

logger = get_logger(__name__)


class ProviderStatisticsTracker:
    """
    Tracks and updates provider_statistics table metrics.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensures the provider_statistics table exists."""
        sql = """
            CREATE TABLE IF NOT EXISTS provider_statistics (
                provider_name TEXT PRIMARY KEY,
                total_opportunities INTEGER DEFAULT 0,
                active_opportunities INTEGER DEFAULT 0,
                average_score REAL DEFAULT 0.0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
        except Exception as e:
            logger.warning(f"Error ensuring provider_statistics table: {e}")

    def update_provider_stats(self, provider_name: str, score: int) -> None:
        """Upserts provider activity record."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO provider_statistics (provider_name, total_opportunities, active_opportunities, average_score, last_seen)
            VALUES (?, 1, 1, ?, ?)
            ON CONFLICT(provider_name) DO UPDATE SET
                total_opportunities = provider_statistics.total_opportunities + 1,
                active_opportunities = provider_statistics.active_opportunities + 1,
                average_score = (provider_statistics.average_score + excluded.average_score) / 2.0,
                last_seen = excluded.last_seen;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (provider_name, float(score), now))
        except Exception as e:
            logger.warning(f"Error updating provider stats for {provider_name}: {e}")

    def recalculate_all(self) -> Dict[str, Any]:
        """
        Recalculates aggregate metrics for all providers from Opportunities.
        Upserts aggregated metrics into provider_statistics.
        """
        self._ensure_table()
        query = """
            SELECT 
                COALESCE(provider, source_id, 'Unknown') as provider_name,
                COUNT(*) as total_opps,
                COUNT(*) FILTER (WHERE lifecycle_status IN ('active', 'closing_soon') AND is_rejected IS NOT TRUE) as active_opps,
                COALESCE(AVG(score), 0.0) as avg_score,
                COALESCE(MAX(last_seen_at), NOW()) as last_seen
            FROM "Opportunities"
            WHERE (provider IS NOT NULL OR source_id IS NOT NULL)
            GROUP BY COALESCE(provider, source_id, 'Unknown');
        """
        upsert_sql = """
            INSERT INTO provider_statistics (provider_name, total_opportunities, active_opportunities, average_score, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (provider_name) DO UPDATE SET
                total_opportunities = excluded.total_opportunities,
                active_opportunities = excluded.active_opportunities,
                average_score = excluded.average_score,
                last_seen = excluded.last_seen;
        """
        updated = 0
        total_opps_sum = 0
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                for r in rows:
                    p_name = r[0] if isinstance(r, (tuple, list)) else r["provider_name"]
                    t_opps = int(r[1] if isinstance(r, (tuple, list)) else r["total_opps"])
                    a_opps = int(r[2] if isinstance(r, (tuple, list)) else r["active_opps"])
                    avg_sc = float(r[3] if isinstance(r, (tuple, list)) else r["avg_score"])
                    l_seen = r[4] if isinstance(r, (tuple, list)) else r["last_seen"]
                    cursor.execute(upsert_sql, (p_name, t_opps, a_opps, avg_sc, l_seen))
                    updated += 1
                    total_opps_sum += t_opps
            return {
                "recalculated_providers": updated,
                "total_opportunities_indexed": total_opps_sum,
            }
        except Exception as e:
            logger.error(f"Failed to recalculate provider statistics: {e}")
            raise


# Backward-compatible and semantic alias
ProviderStatisticsManager = ProviderStatisticsTracker
