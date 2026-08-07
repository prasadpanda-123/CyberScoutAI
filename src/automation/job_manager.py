"""
Background Scan Job Manager for CyberScout AI.

Manages asynchronous scan jobs, single-scan concurrency locking (HTTP 409 Conflict),
progress tracking, and job status reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from src.core.exceptions import CyberScoutError
from src.core.logging import get_logger

logger = get_logger(__name__)


class ScanInProgressError(CyberScoutError):
    """Raised when a scan is requested while another scan is already executing."""
    pass


@dataclass
class ScanJob:
    """Encapsulates execution state, progress metrics, and telemetry for a background scan."""
    job_id: str
    status: str = "queued"  # queued, running, collecting, processing, saving, completed, failed
    progress: float = 0.0  # 0.0 to 100.0
    current_collector: str = "Initializing"
    opportunities_found: int = 0
    elapsed_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    dry_run: bool = False
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Formats scan job status dictionary matching API requirements."""
        now_ts = time.time()
        start_ts = datetime.fromisoformat(self.started_at).timestamp() if self.started_at else now_ts
        finish_ts = datetime.fromisoformat(self.finished_at).timestamp() if self.finished_at else now_ts

        if self.status in ("completed", "failed") and self.finished_at:
            elapsed = round(finish_ts - start_ts, 1)
        elif self.started_at:
            elapsed = round(now_ts - start_ts, 1)
        else:
            elapsed = 0.0

        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": round(self.progress, 1),
            "current_collector": self.current_collector,
            "opportunities_found": self.opportunities_found,
            "elapsed_time": max(0.0, elapsed),
            "errors": self.errors,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "result": self.result,
        }


class ScanJobManager:
    """
    Singleton Manager controlling background scan job creation, locking, and status querying.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._jobs: Dict[str, ScanJob] = {}
        self._active_job_id: Optional[str] = None
        self._job_lock = threading.RLock()
        self._initialized = True

    def is_scan_active(self) -> bool:
        """Returns True if a scan job is currently queued or executing."""
        with self._job_lock:
            if self._active_job_id and self._active_job_id in self._jobs:
                job = self._jobs[self._active_job_id]
                if job.status in ("queued", "running", "collecting", "processing", "saving"):
                    return True
                self._active_job_id = None
            return False

    def get_active_job(self) -> Optional[ScanJob]:
        """Returns currently active ScanJob instance if running, or None."""
        with self._job_lock:
            if self._active_job_id and self._active_job_id in self._jobs:
                job = self._jobs[self._active_job_id]
                if job.status in ("queued", "running", "collecting", "processing", "saving"):
                    return job
            return None

    def start_scan_job(self, dry_run: bool = False, db_manager: Any = None) -> ScanJob:
        """
        Creates and starts a new asynchronous background scan job.

        Args:
            dry_run: Whether scan should run without persisting DB changes.
            db_manager: Optional DatabaseManager instance.

        Returns:
            Created ScanJob instance.

        Raises:
            ScanInProgressError: If another scan job is currently active.
        """
        with self._job_lock:
            if self.is_scan_active():
                active = self.get_active_job()
                active_id = active.job_id if active else "unknown"
                logger.warning(f"Scan request rejected: Scan job '{active_id}' is already in progress.")
                raise ScanInProgressError(f"A scan is already in progress (job_id: {active_id}).")

            job_id = f"job-{uuid.uuid4().hex[:12]}"
            job = ScanJob(job_id=job_id, status="queued", dry_run=dry_run)
            self._jobs[job_id] = job
            self._active_job_id = job_id

            worker_thread = threading.Thread(
                target=self._run_job_worker,
                args=(job, dry_run, db_manager),
                daemon=True,
                name=f"ScanWorker-{job_id}",
            )
            worker_thread.start()

            logger.info(f"Created and launched background scan job '{job_id}'.")
            return job

    def _run_job_worker(self, job: ScanJob, dry_run: bool, db_manager: Any) -> None:
        """Background worker thread executing run_pipeline_once."""
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.status = "running"
        job.progress = 5.0
        job.current_collector = "Initializing Search Planner"

        def progress_cb(stage: str, progress: float, current_collector: str, opp_count: int, error: Optional[str] = None):
            with self._job_lock:
                job.status = stage
                job.progress = min(99.0, max(job.progress, progress))
                if current_collector:
                    job.current_collector = current_collector
                if opp_count > 0:
                    job.opportunities_found = max(job.opportunities_found, opp_count)
                if error:
                    job.errors.append(error)

        try:
            from src.automation.pipeline import run_pipeline_once
            res = run_pipeline_once(
                dry_run=dry_run,
                db_manager=db_manager,
                progress_callback=progress_cb,
            )
            with self._job_lock:
                job.status = "completed"
                job.progress = 100.0
                job.finished_at = datetime.now(timezone.utc).isoformat()
                job.current_collector = "Complete"
                job.opportunities_found = res.get("items_quality_accepted", res.get("accepted", job.opportunities_found))
                job.result = res
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
            logger.info(f"Background scan job '{job.job_id}' completed successfully.")

        except Exception as e:
            with self._job_lock:
                job.status = "failed"
                job.finished_at = datetime.now(timezone.utc).isoformat()
                job.current_collector = "Failed"
                job.errors.append(str(e))
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
            logger.error(f"Background scan job '{job.job_id}' failed: {e}")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Returns status dictionary for specified job_id, or None if not found."""
        with self._job_lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return job.to_dict()

    def clear_completed_jobs(self, keep_last: int = 20) -> None:
        """Cleans up old completed job records from memory."""
        with self._job_lock:
            completed_ids = [jid for jid, j in self._jobs.items() if j.status in ("completed", "failed")]
            if len(completed_ids) > keep_last:
                for jid in completed_ids[:-keep_last]:
                    del self._jobs[jid]


# Module-level singleton instance
scan_job_manager = ScanJobManager()
