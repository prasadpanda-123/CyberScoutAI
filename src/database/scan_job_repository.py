"""
PostgreSQL Persistent Repository for Background Scan Jobs.

Manages persistent operational state, multi-worker concurrency locking (via partial unique index),
progress telemetry, and stale worker recovery.
"""

from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, List, Optional

from src.core.exceptions import DatabaseError, IntegrityError, RepositoryError
from src.core.logging import get_logger
from src.database.base_repository import row_to_dict
from src.database.connection import DatabaseManager

logger = get_logger(__name__)

ACTIVE_STATUSES = ("queued", "running", "collecting", "processing", "saving")
STALE_TIMEOUT_SECONDS = 7200  # 2 hours max lifetime for an in-flight job


class ScanInProgressError(Exception):
    """Raised when a scan is requested while another scan job is currently active."""
    pass


class ScanJobRepository:
    """
    Repository for PostgreSQL 'ScanJobs' operational table.
    Enforces cross-worker concurrency locking so only one active scan can run at a time.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensures 'ScanJobs' table, indexes, and RLS are configured idempotently."""
        sql = """
        CREATE TABLE IF NOT EXISTS "ScanJobs" (
            job_id VARCHAR(64) PRIMARY KEY,
            job_type VARCHAR(32) NOT NULL DEFAULT 'full_scan',
            status VARCHAR(32) NOT NULL DEFAULT 'queued',
            progress REAL NOT NULL DEFAULT 0.0,
            current_collector VARCHAR(128) NOT NULL DEFAULT 'Initializing',
            opportunities_found INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMP NULL,
            finished_at TIMESTAMP NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            dry_run BOOLEAN NOT NULL DEFAULT FALSE,
            errors TEXT NULL,
            result TEXT NULL,
            created_by_admin_id VARCHAR(64) NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scanjobs_status ON "ScanJobs"(status);
        CREATE INDEX IF NOT EXISTS idx_scanjobs_created_at ON "ScanJobs"(created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_scan_job ON "ScanJobs" (job_type)
            WHERE status IN ('queued', 'running', 'collecting', 'processing', 'saving');
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                try:
                    cursor.execute('ALTER TABLE "ScanJobs" ENABLE ROW LEVEL SECURITY;')
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"ScanJobRepository table initialization notice: {e}")

    def _row_to_dict(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Converts raw database row dictionary to standardized ScanJob dictionary."""
        now_ts = time.time()
        started_at = row_data.get("started_at")
        finished_at = row_data.get("finished_at")
        created_at = row_data.get("created_at")

        start_iso = started_at.isoformat() if hasattr(started_at, "isoformat") else (str(started_at) if started_at else None)
        finish_iso = finished_at.isoformat() if hasattr(finished_at, "isoformat") else (str(finished_at) if finished_at else None)
        created_iso = created_at.isoformat() if hasattr(created_at, "isoformat") else (str(created_at) if created_at else datetime.now(timezone.utc).isoformat())

        start_ts = None
        if started_at:
            try:
                start_ts = started_at.timestamp() if hasattr(started_at, "timestamp") else datetime.fromisoformat(str(started_at)).timestamp()
            except Exception:
                start_ts = None

        finish_ts = None
        if finished_at:
            try:
                finish_ts = finished_at.timestamp() if hasattr(finished_at, "timestamp") else datetime.fromisoformat(str(finished_at)).timestamp()
            except Exception:
                finish_ts = None

        status = str(row_data.get("status", "queued"))
        if status in ("completed", "failed") and finish_ts and start_ts:
            elapsed = round(finish_ts - start_ts, 1)
        elif start_ts:
            elapsed = round(now_ts - start_ts, 1)
        else:
            elapsed = 0.0

        errors_val = row_data.get("errors")
        err_list = []
        if errors_val:
            if isinstance(errors_val, list):
                err_list = errors_val
            elif isinstance(errors_val, str):
                try:
                    err_list = json.loads(errors_val)
                except Exception:
                    err_list = [errors_val]

        result_val = row_data.get("result")
        res_dict = None
        if result_val:
            if isinstance(result_val, dict):
                res_dict = result_val
            elif isinstance(result_val, str):
                try:
                    res_dict = json.loads(result_val)
                except Exception:
                    res_dict = None

        return {
            "job_id": row_data.get("job_id"),
            "job_type": row_data.get("job_type", "full_scan"),
            "status": status,
            "progress": round(float(row_data.get("progress", 0.0)), 1),
            "current_collector": row_data.get("current_collector", "Initializing"),
            "opportunities_found": int(row_data.get("opportunities_found", 0)),
            "elapsed_time": max(0.0, elapsed),
            "errors": err_list,
            "created_at": created_iso,
            "started_at": start_iso,
            "finished_at": finish_iso,
            "dry_run": bool(row_data.get("dry_run", False)),
            "result": res_dict,
            "created_by_admin_id": row_data.get("created_by_admin_id"),
        }

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves scan job record by job_id."""
        if not job_id or not isinstance(job_id, str):
            return None

        sql = 'SELECT * FROM "ScanJobs" WHERE job_id = %s LIMIT 1;'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (job_id.strip(),))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row_to_dict(row, cursor.description))
        except Exception as e:
            logger.warning(f"Error querying scan job '{job_id}': {e}")
            return None
        finally:
            cursor.close()

    def get_active_job(self) -> Optional[Dict[str, Any]]:
        """Queries currently active (queued/running) scan job if present."""
        sql = """
        SELECT * FROM "ScanJobs"
        WHERE status IN ('queued', 'running', 'collecting', 'processing', 'saving')
        ORDER BY created_at DESC
        LIMIT 1;
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row_to_dict(row, cursor.description))
        except Exception as e:
            logger.debug(f"Error querying active scan job: {e}")
            return None
        finally:
            cursor.close()

    def is_scan_active(self) -> bool:
        """
        Returns True if a scan job is currently queued or executing.
        Recovers from stale crashed worker jobs (>2h) automatically.
        """
        active_job = self.get_active_job()
        if not active_job:
            return False

        # Stale job detection
        created_at_str = active_job.get("created_at")
        if created_at_str:
            try:
                created_dt = datetime.fromisoformat(created_at_str)
                age = (datetime.now(timezone.utc) - created_dt.replace(tzinfo=timezone.utc)).total_seconds()
                if age > STALE_TIMEOUT_SECONDS:
                    stale_id = active_job["job_id"]
                    logger.warning(f"Active scan job '{stale_id}' is stale (>2h, age={age:.0f}s). Marking as failed.")
                    self.mark_failed(stale_id, "Job exceeded maximum execution timeout (stale worker recovery).")
                    return False
            except Exception as e:
                logger.debug(f"Could not compute stale job age: {e}")

        return True

    def recover_stuck_jobs(self, timeout_seconds: Optional[int] = None) -> List[str]:
        """
        Discovers and safely recovers any active jobs that have remained in 'queued'
        or 'running' beyond timeout threshold (default STALE_TIMEOUT_SECONDS).

        Returns:
            List of recovered job_id strings.
        """
        threshold = STALE_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        recovered_ids: List[str] = []
        active_job = self.get_active_job()
        if not active_job:
            return []

        created_at_str = active_job.get("created_at") or active_job.get("started_at")
        if created_at_str:
            try:
                created_dt = datetime.fromisoformat(str(created_at_str))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - created_dt).total_seconds()
                if age >= threshold:
                    stale_id = str(active_job["job_id"])
                    logger.warning(
                        f"Recovering stuck scan job '{stale_id}' (status='{active_job.get('status')}', age={age:.0f}s >= {threshold}s)."
                    )
                    self.mark_failed(stale_id, f"Job exceeded execution timeout ({age:.0f}s >= {threshold}s). Safely recovered.")
                    recovered_ids.append(stale_id)
            except Exception as e:
                logger.error(f"Error evaluating stuck job for recovery: {e}")

        return recovered_ids

    def create_job(
        self,
        job_id: str,
        job_type: str = "full_scan",
        dry_run: bool = False,
        created_by_admin_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new persistent scan job in PostgreSQL.

        Enforces concurrency locking:
        1. Pre-check for active job.
        2. Partial unique index 'uq_active_scan_job' enforces lock at database engine level.

        Raises:
            ScanInProgressError: If another scan job is currently active.
        """
        if self.is_scan_active():
            active = self.get_active_job()
            active_id = active.get("job_id") if active else "unknown"
            logger.warning(f"Scan request rejected: Scan job '{active_id}' is already active.")
            raise ScanInProgressError(f"A scan is already in progress (job_id: {active_id}).")

        now = datetime.now(timezone.utc)
        sql = """
        INSERT INTO "ScanJobs" (
            job_id, job_type, status, progress, current_collector,
            opportunities_found, started_at, finished_at, created_at,
            updated_at, dry_run, errors, result, created_by_admin_id
        ) VALUES (
            %s, %s, 'queued', 0.0, 'Initializing',
            0, NULL, NULL, %s,
            %s, %s, '[]', NULL, %s
        );
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (job_id, job_type, now, now, dry_run, created_by_admin_id),
                )
            logger.info(f"Persisted new scan job '{job_id}' (dry_run={dry_run}) in PostgreSQL.")
            return self.get_job(job_id) or {"job_id": job_id, "status": "queued"}
        except (IntegrityError, Exception) as e:
            err_msg = str(e)
            if "uq_active_scan_job" in err_msg or "duplicate key" in err_msg.lower() or "unique" in err_msg.lower():
                active = self.get_active_job()
                active_id = active.get("job_id") if active else "unknown"
                logger.warning(f"Concurrency lock: Unique constraint prevented duplicate scan '{job_id}'. Active: {active_id}")
                raise ScanInProgressError(f"A scan is already in progress (job_id: {active_id}).") from e
            raise RepositoryError(f"Failed to create scan job '{job_id}': {e}", original_exception=e)

    def mark_running(self, job_id: str) -> bool:
        """Transitions job to 'running' state with started_at timestamp."""
        now = datetime.now(timezone.utc)
        sql = """
        UPDATE "ScanJobs"
        SET status = 'running',
            progress = 5.0,
            current_collector = 'Initializing Search Planner',
            started_at = %s,
            updated_at = %s
        WHERE job_id = %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (now, now, job_id))
            return True
        except Exception as e:
            logger.warning(f"Failed to mark scan job '{job_id}' running: {e}")
            return False

    def update_progress(
        self,
        job_id: str,
        stage: str,
        progress: float,
        current_collector: Optional[str] = None,
        opp_count: int = 0,
        error: Optional[str] = None,
    ) -> bool:
        """Updates progress telemetry for an in-flight job."""
        now = datetime.now(timezone.utc)
        job = self.get_job(job_id)
        if not job:
            return False

        existing_errors = job.get("errors", [])
        if error and error not in existing_errors:
            existing_errors.append(error)
        errors_json = json.dumps(existing_errors)

        collector = current_collector or job.get("current_collector", "Executing")
        opportunities = max(job.get("opportunities_found", 0), opp_count)
        clamped_progress = min(99.0, max(job.get("progress", 0.0), float(progress)))

        sql = """
        UPDATE "ScanJobs"
        SET status = %s,
            progress = %s,
            current_collector = %s,
            opportunities_found = %s,
            errors = %s,
            updated_at = %s
        WHERE job_id = %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (stage, clamped_progress, collector, opportunities, errors_json, now, job_id))
            return True
        except Exception as e:
            logger.debug(f"Failed to update progress for scan job '{job_id}': {e}")
            return False

    def mark_completed(
        self,
        job_id: str,
        opportunities_found: int = 0,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Transitions job to 'completed' state and records final metrics."""
        now = datetime.now(timezone.utc)
        res_json = json.dumps(result, default=str) if result else None
        sql = """
        UPDATE "ScanJobs"
        SET status = 'completed',
            progress = 100.0,
            current_collector = 'Complete',
            opportunities_found = GREATEST(opportunities_found, %s),
            result = %s,
            finished_at = %s,
            updated_at = %s
        WHERE job_id = %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (opportunities_found, res_json, now, now, job_id))
            logger.info(f"Scan job '{job_id}' marked COMPLETED in PostgreSQL.")
            return True
        except Exception as e:
            logger.warning(f"Failed to mark scan job '{job_id}' completed: {e}")
            return False

    def mark_failed(self, job_id: str, error: str) -> bool:
        """Transitions job to 'failed' state and logs safe error message."""
        now = datetime.now(timezone.utc)
        job = self.get_job(job_id)
        existing_errors = job.get("errors", []) if job else []
        if error and error not in existing_errors:
            existing_errors.append(error)
        errors_json = json.dumps(existing_errors)

        sql = """
        UPDATE "ScanJobs"
        SET status = 'failed',
            current_collector = 'Failed',
            errors = %s,
            finished_at = %s,
            updated_at = %s
        WHERE job_id = %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (errors_json, now, now, job_id))
            logger.info(f"Scan job '{job_id}' marked FAILED in PostgreSQL.")
            return True
        except Exception as e:
            logger.warning(f"Failed to mark scan job '{job_id}' failed: {e}")
            return False

    def list_recent_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent scan jobs ordered by creation timestamp descending."""
        sql = 'SELECT * FROM "ScanJobs" ORDER BY created_at DESC LIMIT %s;'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            return [self._row_to_dict(row_to_dict(r, cursor.description)) for r in rows]
        except Exception as e:
            logger.warning(f"Error listing recent scan jobs: {e}")
            return []
        finally:
            cursor.close()
