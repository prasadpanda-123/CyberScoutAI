"""
Action Job Manager for CyberScout AI.

Provides real-time tracking, stage updates, and progress reporting for all
administrative and system control actions executed via the admin dashboard.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ActionJob:
    """Encapsulates execution state, progress, and stage reporting for an action."""
    job_id: str
    action_name: str
    action_label: str
    status: str = "QUEUED"  # QUEUED, STARTING, RUNNING, COMPLETED, FAILED, CANCELLED, PAUSED
    progress: Optional[float] = 0.0  # None or float 0-100
    current_stage: str = "Queued"
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_update_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Formats the action job dictionary for JSON serialization."""
        now_ts = time.time()
        try:
            start_ts = datetime.fromisoformat(self.start_time).timestamp()
        except Exception:
            start_ts = now_ts

        if self.end_time:
            try:
                end_ts = datetime.fromisoformat(self.end_time).timestamp()
                elapsed = round(max(0.0, end_ts - start_ts), 1)
            except Exception:
                elapsed = round(max(0.0, now_ts - start_ts), 1)
        else:
            elapsed = round(max(0.0, now_ts - start_ts), 1)

        return {
            "job_id": self.job_id,
            "action_name": self.action_name,
            "action_label": self.action_label,
            "status": self.status,
            "progress": round(self.progress, 1) if isinstance(self.progress, (int, float)) else None,
            "current_stage": self.current_stage,
            "start_time": self.start_time,
            "last_update_time": self.last_update_time,
            "end_time": self.end_time,
            "elapsed_seconds": elapsed,
            "result": self.result,
            "error": self.error,
            "details": self.details,
            "success": self.status == "COMPLETED",
        }


class ActionJobManager:
    """
    Singleton manager controlling action job tracking, lifecycle management,
    and progress dispatch.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._jobs: Dict[str, ActionJob] = {}
        self._active_job_id: Optional[str] = None
        self._job_lock = threading.RLock()
        self._initialized = True

    def is_action_active(self) -> bool:
        """Checks if any action is currently queued, starting, or running."""
        with self._job_lock:
            # First check local action jobs
            if self._active_job_id and self._active_job_id in self._jobs:
                job = self._jobs[self._active_job_id]
                if job.status in ("QUEUED", "STARTING", "RUNNING"):
                    return True
                self._active_job_id = None

            # Next check scan job manager
            try:
                from src.automation.job_manager import scan_job_manager
                if scan_job_manager.is_scan_active():
                    return True
            except Exception:
                pass

            return False

    def get_active_action(self) -> Optional[Dict[str, Any]]:
        """Returns the currently executing action job, or None."""
        with self._job_lock:
            if self._active_job_id and self._active_job_id in self._jobs:
                job = self._jobs[self._active_job_id]
                if job.status in ("QUEUED", "STARTING", "RUNNING"):
                    return job.to_dict()
                self._active_job_id = None

            # Fallback to scan job manager if an active scan is running
            try:
                from src.automation.job_manager import scan_job_manager
                scan_job = scan_job_manager.get_active_job()
                if scan_job:
                    return self._map_scan_job_to_action_dict(scan_job)
            except Exception:
                pass

            return None

    def _map_scan_job_to_action_dict(self, scan_job: Any) -> Dict[str, Any]:
        """Translates a ScanJob object or dict into a standardized action job dictionary."""
        d = scan_job.to_dict() if hasattr(scan_job, "to_dict") else dict(scan_job)
        status_raw = (d.get("status") or "running").upper()
        if status_raw in ("SUCCESS", "COMPLETED"):
            status = "COMPLETED"
        elif status_raw in ("FAILED", "ERROR"):
            status = "FAILED"
        elif status_raw in ("QUEUED", "STARTING"):
            status = status_raw
        else:
            status = "RUNNING"

        err = None
        if d.get("errors"):
            err = "; ".join(str(e) for e in d["errors"]) if isinstance(d["errors"], list) else str(d["errors"])

        return {
            "job_id": d.get("job_id"),
            "action_name": "execute_scan",
            "action_label": "Execute Scan",
            "status": status,
            "progress": d.get("progress", 0.0),
            "current_stage": d.get("current_collector") or "Executing scan pipeline",
            "start_time": d.get("started_at") or d.get("created_at"),
            "last_update_time": datetime.now(timezone.utc).isoformat(),
            "end_time": d.get("finished_at"),
            "elapsed_seconds": d.get("elapsed_time", 0.0),
            "result": d.get("result") or {"opportunities_found": d.get("opportunities_found", 0)},
            "error": err,
            "details": {
                "opportunities_found": d.get("opportunities_found", 0),
                "dry_run": d.get("dry_run", False),
            },
            "success": status == "COMPLETED",
        }

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an action job status by job_id."""
        with self._job_lock:
            if job_id in self._jobs:
                return self._jobs[job_id].to_dict()

        # Fallback to scan_job_manager for scan jobs
        try:
            from src.automation.job_manager import scan_job_manager
            scan_dict = scan_job_manager.get_job(job_id)
            if scan_dict:
                return self._map_scan_job_to_action_dict(scan_dict)
        except Exception:
            pass

        return None

    def start_action(
        self,
        action_name: str,
        action_label: str,
        task_fn: Callable[[Callable[[str, Optional[float], Optional[Dict[str, Any]]], None]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Starts an asynchronous tracked action job.

        Args:
            action_name: Key identifier for the action (e.g. 'send_test_email').
            action_label: Human-friendly name (e.g. 'Send Test Email').
            task_fn: Callable taking progress_callback(stage, progress, details).

        Returns:
            Initial job dictionary.
        """
        with self._job_lock:
            if self.is_action_active():
                active = self.get_active_action()
                active_lbl = active.get("action_label", "Another operation") if active else "Another operation"
                raise RuntimeError(f"Cannot start '{action_label}': {active_lbl} is currently in progress.")

            job_id = f"act-{uuid.uuid4().hex[:12]}"
            job = ActionJob(
                job_id=job_id,
                action_name=action_name,
                action_label=action_label,
                status="STARTING",
                progress=0.0,
                current_stage="Initializing",
            )
            self._jobs[job_id] = job
            self._active_job_id = job_id

            worker_thread = threading.Thread(
                target=self._run_worker,
                args=(job, task_fn),
                daemon=True,
                name=f"ActionWorker-{job_id}",
            )
            worker_thread.start()
            return job.to_dict()

    def _run_worker(
        self,
        job: ActionJob,
        task_fn: Callable[[Callable[[str, Optional[float], Optional[Dict[str, Any]]], None]], Dict[str, Any]],
    ) -> None:
        """Executes the action task function inside background worker thread."""
        job.status = "RUNNING"
        job.last_update_time = datetime.now(timezone.utc).isoformat()

        def update_progress(stage: str, progress: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
            with self._job_lock:
                job.current_stage = stage
                if progress is not None:
                    job.progress = min(100.0, max(0.0, float(progress)))
                if details:
                    job.details.update(details)
                job.last_update_time = datetime.now(timezone.utc).isoformat()

        try:
            result = task_fn(update_progress)
            with self._job_lock:
                job.status = "COMPLETED"
                job.progress = 100.0
                job.current_stage = "Completed successfully"
                job.end_time = datetime.now(timezone.utc).isoformat()
                job.result = result if isinstance(result, dict) else {"result": result}
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
            logger.info(f"Action '{job.action_name}' ({job.job_id}) completed successfully.")
        except Exception as e:
            with self._job_lock:
                job.status = "FAILED"
                job.current_stage = "Failed"
                job.end_time = datetime.now(timezone.utc).isoformat()
                job.error = str(e)
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
            logger.error(f"Action '{job.action_name}' ({job.job_id}) failed: {e}")

        # Keep memory clean
        self._prune_history()

    def create_instant_completed_job(
        self,
        action_name: str,
        action_label: str,
        result: Dict[str, Any],
        stage: str = "Completed successfully",
    ) -> Dict[str, Any]:
        """Creates a record for synchronous instant actions (e.g. ping, pause, db_info)."""
        with self._job_lock:
            job_id = f"act-{uuid.uuid4().hex[:12]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            clean_result = dict(result) if isinstance(result, dict) else result
            job = ActionJob(
                job_id=job_id,
                action_name=action_name,
                action_label=action_label,
                status="COMPLETED",
                progress=100.0,
                current_stage=stage,
                start_time=now_iso,
                last_update_time=now_iso,
                end_time=now_iso,
                result=clean_result,
            )
            self._jobs[job_id] = job

            self._prune_history()
            return job.to_dict()

    def create_instant_failed_job(
        self,
        action_name: str,
        action_label: str,
        error: str,
        stage: str = "Failed",
    ) -> Dict[str, Any]:
        """Creates a record for failed instant actions."""
        with self._job_lock:
            job_id = f"act-{uuid.uuid4().hex[:12]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            job = ActionJob(
                job_id=job_id,
                action_name=action_name,
                action_label=action_label,
                status="FAILED",
                progress=100.0,
                current_stage=stage,
                start_time=now_iso,
                last_update_time=now_iso,
                end_time=now_iso,
                error=error,
            )
            self._jobs[job_id] = job
            self._prune_history()
            return job.to_dict()

    def _prune_history(self, keep_last: int = 50) -> None:
        """Keeps recent action jobs in memory, trimming oldest completed."""
        with self._job_lock:
            completed_keys = [
                jid for jid, j in self._jobs.items()
                if j.status in ("COMPLETED", "FAILED", "CANCELLED")
            ]
            if len(completed_keys) > keep_last:
                for jid in completed_keys[:-keep_last]:
                    del self._jobs[jid]


# Global singleton instance
action_job_manager = ActionJobManager()
