"""
History Repository for CyberScout AI.

Manages SearchHistory and EmailHistory logging in SQLite.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import uuid

from src.database.connection import DatabaseManager
from src.core.exceptions import DatabaseError
from src.core.logging import get_logger

logger = get_logger(__name__)


class SearchHistoryRepository:
    """
    DAO for recording pipeline runs in SearchHistory table.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def start_run(self, run_id: str, sources_run: List[str]) -> None:
        """Logs the start of a pipeline run."""
        sql = """
        INSERT INTO SearchHistory (
            run_id, triggered_at, status, sources_run,
            items_collected, items_after_dedup, items_emailed, errors
        ) VALUES (?, ?, ?, ?, 0, 0, 0, ?);
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (run_id, now, "running", json.dumps(sources_run), json.dumps([])),
                )
            logger.info(f"Started tracking pipeline run '{run_id}'.")
        except Exception as e:
            raise DatabaseError(f"Failed to record run start for '{run_id}': {e}", original_exception=e)

    def complete_run(
        self,
        run_id: str,
        status: str = "success",
        items_collected: int = 0,
        items_after_dedup: int = 0,
        items_emailed: int = 0,
        errors: Optional[List[str]] = None,
    ) -> None:
        """Logs the completion of a pipeline run."""
        sql = """
        UPDATE SearchHistory SET
            completed_at = ?,
            status = ?,
            items_collected = ?,
            items_after_dedup = ?,
            items_emailed = ?,
            errors = ?
        WHERE run_id = ?;
        """
        now = datetime.now(timezone.utc).isoformat()
        err_json = json.dumps(errors or [])
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (
                        now,
                        status,
                        items_collected,
                        items_after_dedup,
                        items_emailed,
                        err_json,
                        run_id,
                    ),
                )
            logger.info(f"Completed tracking pipeline run '{run_id}' with status '{status}'.")
        except Exception as e:
            raise DatabaseError(f"Failed to record run completion for '{run_id}': {e}", original_exception=e)


class EmailHistoryRepository:
    """
    DAO for tracking sent opportunity digests in EmailHistory table.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def record_emailed_opportunity(self, opportunity_id: str, email_run_id: str) -> None:
        """Records an opportunity as sent in an email digest."""
        sql = """
        INSERT INTO EmailHistory (id, opportunity_id, email_run_id, sent_at, clicked)
        VALUES (?, ?, ?, ?, 0);
        """
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (record_id, opportunity_id, email_run_id, now))
        except Exception as e:
            raise DatabaseError(f"Failed to record email history for '{opportunity_id}': {e}", original_exception=e)

    def is_already_emailed(self, opportunity_id: str) -> bool:
        """Checks if an opportunity was previously sent in an email digest."""
        sql = "SELECT COUNT(*) as cnt FROM EmailHistory WHERE opportunity_id = ?;"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (opportunity_id,))
            row = cursor.fetchone()
            return row["cnt"] > 0 if row else False
        finally:
            cursor.close()
