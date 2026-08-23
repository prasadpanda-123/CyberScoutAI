"""
Webhook Request Repository for CyberScout AI.

Provides database persistence and replay-prevention lookup for external scheduler webhook triggers.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.database.connection import DatabaseManager

logger = get_logger(__name__)


class WebhookRequestRepository:
    """
    Repository managing PostgreSQL scheduler_webhook_requests table persistence and idempotency checks.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensures scheduler_webhook_requests table exists."""
        sql = """
        CREATE TABLE IF NOT EXISTS scheduler_webhook_requests (
            id SERIAL PRIMARY KEY,
            request_id VARCHAR(128) UNIQUE NOT NULL,
            timestamp BIGINT NOT NULL,
            received_at TIMESTAMP NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'accepted',
            source VARCHAR(64) NOT NULL DEFAULT 'google_apps_script',
            execution_details TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_webhook_req_id ON scheduler_webhook_requests(request_id);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
        except Exception as e:
            logger.debug(f"WebhookRequestRepository: table initialization note: {e}")

    def get_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a webhook request record by unique request_id.
        """
        if not request_id or not isinstance(request_id, str):
            return None

        clean_id = request_id.strip()
        sql = """
        SELECT id, request_id, timestamp, received_at, status, source, execution_details
        FROM scheduler_webhook_requests
        WHERE request_id = ?
        LIMIT 1;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (clean_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "request_id": row["request_id"],
                    "timestamp": row["timestamp"],
                    "received_at": str(row["received_at"]),
                    "status": row["status"],
                    "source": row["source"],
                    "execution_details": row["execution_details"],
                }
        except Exception as e:
            logger.error(f"Error querying webhook request_id '{clean_id}': {e}")
            return None

    def record_request(
        self,
        request_id: str,
        timestamp: int,
        source: str = "google_apps_script",
        status: str = "accepted",
        execution_details: Optional[str] = None,
    ) -> bool:
        """
        Registers a new incoming webhook trigger request.
        Fails if request_id already exists (unique constraint violation).
        """
        if not request_id or not isinstance(request_id, str):
            return False

        clean_id = request_id.strip()
        now_dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        INSERT INTO scheduler_webhook_requests (request_id, timestamp, received_at, status, source, execution_details)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (clean_id, int(timestamp), now_dt, status, source, execution_details),
                )
            logger.info(f"Registered external webhook trigger request '{clean_id}' from source '{source}'.")
            return True
        except Exception as e:
            logger.warning(f"Could not register webhook request '{clean_id}' (possible duplicate): {e}")
            return False

    def update_status(
        self,
        request_id: str,
        status: str,
        execution_details: Optional[str] = None,
    ) -> bool:
        """
        Updates execution status and details for an existing request_id.
        """
        if not request_id:
            return False

        clean_id = request_id.strip()
        sql = """
        UPDATE scheduler_webhook_requests
        SET status = ?, execution_details = ?
        WHERE request_id = ?;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (status, execution_details, clean_id))
            logger.info(f"Updated webhook request '{clean_id}' status to '{status}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to update webhook request '{clean_id}' status: {e}")
            return False

    def get_latest_trigger(self) -> Optional[Dict[str, Any]]:
        """
        Returns the most recently recorded webhook trigger event.
        """
        sql = """
        SELECT id, request_id, timestamp, received_at, status, source, execution_details
        FROM scheduler_webhook_requests
        ORDER BY id DESC
        LIMIT 1;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "request_id": row["request_id"],
                    "timestamp": row["timestamp"],
                    "received_at": str(row["received_at"]),
                    "status": row["status"],
                    "source": row["source"],
                    "execution_details": row["execution_details"],
                }
        except Exception as e:
            logger.error(f"Error querying latest webhook trigger: {e}")
            return None
