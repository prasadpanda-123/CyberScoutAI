"""
Scheduler State Repository for CyberScout AI.

Manages persistent tracking of last_email_sent, last_pipeline_run, and updated_at
in PostgreSQL to ensure restart safety and prevent duplicate daily email delivery.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.core.logging import get_logger
from src.database.connection import DatabaseManager

logger = get_logger(__name__)


class SchedulerRepository:
    """
    Repository managing PostgreSQL scheduler_state table persistence.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def get_state(self) -> Dict[str, Any]:
        """
        Retrieves current scheduler state from PostgreSQL database.
        Ensures a default row exists if missing.

        Returns:
            Dictionary containing 'last_email_sent', 'last_pipeline_run', and 'updated_at'.
        """
        sql = "SELECT id, last_email_sent, last_pipeline_run, updated_at FROM scheduler_state WHERE id = 1;"
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                if not row:
                    now = datetime.now(timezone.utc).isoformat()
                    cursor.execute(
                        "INSERT INTO scheduler_state (id, last_email_sent, last_pipeline_run, updated_at) VALUES (1, '', '', ?);",
                        (now,),
                    )
                    return {"last_email_sent": "", "last_pipeline_run": "", "updated_at": now}
                
                return {
                    "last_email_sent": row["last_email_sent"] or "",
                    "last_pipeline_run": row["last_pipeline_run"] or "",
                    "updated_at": row["updated_at"] or "",
                }
        except Exception as e:
            logger.error(f"Error fetching scheduler state from database: {e}")
            return {"last_email_sent": "", "last_pipeline_run": "", "updated_at": ""}

    def update_last_email_sent(self, date_str: str, pipeline_run_time: Optional[str] = None) -> bool:
        """
        Updates last_email_sent date string and updated_at timestamp.

        Args:
            date_str: Date string formatted as YYYY-MM-DD.
            pipeline_run_time: Optional ISO timestamp of the corresponding pipeline run.

        Returns:
            True if updated successfully, False otherwise.
        """
        now = datetime.now(timezone.utc).isoformat()
        pipe_time = pipeline_run_time or now
        
        sql = """
        INSERT INTO scheduler_state (id, last_email_sent, last_pipeline_run, updated_at)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_email_sent = excluded.last_email_sent,
            last_pipeline_run = CASE WHEN excluded.last_pipeline_run != '' THEN excluded.last_pipeline_run ELSE scheduler_state.last_pipeline_run END,
            updated_at = excluded.updated_at;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (date_str, pipe_time, now))
            logger.info(f"Updated scheduler_state: last_email_sent='{date_str}'")
            return True
        except Exception as e:
            logger.error(f"Failed to update last_email_sent in scheduler_state: {e}")
            return False

    def update_last_pipeline_run(self, pipeline_run_time: str) -> bool:
        """
        Updates last_pipeline_run timestamp.

        Args:
            pipeline_run_time: ISO timestamp string.

        Returns:
            True if updated successfully, False otherwise.
        """
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT INTO scheduler_state (id, last_email_sent, last_pipeline_run, updated_at)
        VALUES (1, '', ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_pipeline_run = excluded.last_pipeline_run,
            updated_at = excluded.updated_at;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (pipeline_run_time, now))
            logger.info(f"Updated scheduler_state: last_pipeline_run='{pipeline_run_time}'")
            return True
        except Exception as e:
            logger.error(f"Failed to update last_pipeline_run in scheduler_state: {e}")
            return False
