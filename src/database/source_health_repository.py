"""
Source Health Repository for CyberScout AI (Phase 2).

Provides persistence and query capabilities for source health telemetry records in PostgreSQL/SQLite.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.collectors.source_health import SourceHealthRecord
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.models.enums import HealthStatus

logger = get_logger(__name__)


class SourceHealthRepository:
    """
    DAO for managing SourceHealth records.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensures the SourceHealth table exists."""
        sql = """
        CREATE TABLE IF NOT EXISTS "SourceHealth" (
            source_id VARCHAR(128) PRIMARY KEY,
            health_status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY',
            last_attempt TIMESTAMP NULL,
            last_success TIMESTAMP NULL,
            last_failure TIMESTAMP NULL,
            failure_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            items_seen INTEGER NOT NULL DEFAULT 0,
            items_created INTEGER NOT NULL DEFAULT 0,
            items_updated INTEGER NOT NULL DEFAULT 0,
            items_rejected INTEGER NOT NULL DEFAULT 0,
            latency REAL NOT NULL DEFAULT 0.0,
            error_class VARCHAR(64) NULL,
            parser_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            details TEXT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_source_health_status ON "SourceHealth"(health_status);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.executescript(sql)
        except Exception as e:
            logger.debug(f"SourceHealth table check: {e}")

    def save_health_record(self, record: SourceHealthRecord) -> str:
        """Upserts a source health telemetry record."""
        sql = """
        INSERT INTO "SourceHealth" (
            source_id, health_status, last_attempt, last_success, last_failure,
            failure_count, success_count, items_seen, items_created,
            items_updated, items_rejected, latency, error_class,
            parser_version, consecutive_failures, details, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        ON CONFLICT(source_id) DO UPDATE SET
            health_status = excluded.health_status,
            last_attempt = excluded.last_attempt,
            last_success = excluded.last_success,
            last_failure = excluded.last_failure,
            failure_count = excluded.failure_count,
            success_count = excluded.success_count,
            items_seen = excluded.items_seen,
            items_created = excluded.items_created,
            items_updated = excluded.items_updated,
            items_rejected = excluded.items_rejected,
            latency = excluded.latency,
            error_class = excluded.error_class,
            parser_version = excluded.parser_version,
            consecutive_failures = excluded.consecutive_failures,
            details = excluded.details,
            updated_at = excluded.updated_at;
        """
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        status_val = record.health_status.value if hasattr(record.health_status, "value") else str(record.health_status)
        values = (
            record.source_id,
            status_val,
            record.last_attempt,
            record.last_success,
            record.last_failure,
            int(record.failure_count or 0),
            int(record.success_count or 0),
            int(record.items_seen or 0),
            int(record.items_created or 0),
            int(record.items_updated or 0),
            int(record.items_rejected or 0),
            float(record.latency or 0.0),
            record.error_class,
            record.parser_version or "1.0.0",
            int(record.consecutive_failures or 0),
            record.last_error_message,
            now_ts,
        )
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
            return record.source_id
        except Exception as e:
            logger.error(f"Failed to save source health for '{record.source_id}': {e}")
            raise RepositoryError(f"Failed to save source health: {e}", original_exception=e)

    def get_health_record(self, source_id: str) -> Optional[SourceHealthRecord]:
        """Retrieves the health record for a source."""
        sql = """
        SELECT source_id, health_status, last_attempt, last_success, last_failure,
               failure_count, success_count, items_seen, items_created,
               items_updated, items_rejected, latency, error_class,
               parser_version, consecutive_failures, details, updated_at
        FROM "SourceHealth"
        WHERE source_id = ?
        LIMIT 1;
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (source_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None

            def _get(key, idx, default=None):
                if hasattr(row, "keys") and key in row.keys():
                    return row[key]
                elif hasattr(row, key):
                    return getattr(row, key)
                elif isinstance(row, (tuple, list)) and idx < len(row):
                    return row[idx]
                return default

            status_str = _get("health_status", 1, HealthStatus.HEALTHY.value)
            return SourceHealthRecord(
                source_id=_get("source_id", 0, source_id),
                health_status=status_str,
                last_attempt=str(_get("last_attempt", 2)) if _get("last_attempt", 2) else None,
                last_success=str(_get("last_success", 3)) if _get("last_success", 3) else None,
                last_failure=str(_get("last_failure", 4)) if _get("last_failure", 4) else None,
                failure_count=int(_get("failure_count", 5, 0) or 0),
                success_count=int(_get("success_count", 6, 0) or 0),
                items_seen=int(_get("items_seen", 7, 0) or 0),
                items_created=int(_get("items_created", 8, 0) or 0),
                items_updated=int(_get("items_updated", 9, 0) or 0),
                items_rejected=int(_get("items_rejected", 10, 0) or 0),
                latency=float(_get("latency", 11, 0.0) or 0.0),
                error_class=_get("error_class", 12),
                parser_version=_get("parser_version", 13, "1.0.0"),
                consecutive_failures=int(_get("consecutive_failures", 14, 0) or 0),
                last_error_message=_get("details", 15),
            )
        except Exception as e:
            logger.error(f"Failed to fetch health record for '{source_id}': {e}")
            return None

    def get_all_health_records(self) -> List[SourceHealthRecord]:
        """Retrieves all source health records."""
        sql = """
        SELECT source_id, health_status, last_attempt, last_success, last_failure,
               failure_count, success_count, items_seen, items_created,
               items_updated, items_rejected, latency, error_class,
               parser_version, consecutive_failures, details, updated_at
        FROM "SourceHealth"
        ORDER BY source_id ASC;
        """
        records = []
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
            for row in rows:
                def _get(key, idx, default=None):
                    if hasattr(row, "keys") and key in row.keys():
                        return row[key]
                    elif hasattr(row, key):
                        return getattr(row, key)
                    elif isinstance(row, (tuple, list)) and idx < len(row):
                        return row[idx]
                    return default

                records.append(
                    SourceHealthRecord(
                        source_id=_get("source_id", 0, ""),
                        health_status=_get("health_status", 1, HealthStatus.HEALTHY.value),
                        last_attempt=str(_get("last_attempt", 2)) if _get("last_attempt", 2) else None,
                        last_success=str(_get("last_success", 3)) if _get("last_success", 3) else None,
                        last_failure=str(_get("last_failure", 4)) if _get("last_failure", 4) else None,
                        failure_count=int(_get("failure_count", 5, 0) or 0),
                        success_count=int(_get("success_count", 6, 0) or 0),
                        items_seen=int(_get("items_seen", 7, 0) or 0),
                        items_created=int(_get("items_created", 8, 0) or 0),
                        items_updated=int(_get("items_updated", 9, 0) or 0),
                        items_rejected=int(_get("items_rejected", 10, 0) or 0),
                        latency=float(_get("latency", 11, 0.0) or 0.0),
                        error_class=_get("error_class", 12),
                        parser_version=_get("parser_version", 13, "1.0.0"),
                        consecutive_failures=int(_get("consecutive_failures", 14, 0) or 0),
                        last_error_message=_get("details", 15),
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch all health records: {e}")
        return records
