"""
Scheduler service for background daemon loop execution.
"""

from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger
from src.automation.jobs import ScheduledJob

logger = get_logger(__name__)


class SchedulerService:
    """
    Background scheduler runner driving job tasks.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (CONFIG_DIR / "scheduler.yaml")
        self.jobs: List[ScheduledJob] = []
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self.schedule_type = "daily"
        self.interval_seconds = 86400
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads schedule interval parameters from YAML configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                sched = data.get("schedule", {})
                self.schedule_type = sched.get("type", "daily")
                if self.schedule_type == "hourly":
                    self.interval_seconds = 3600
                elif self.schedule_type == "6_hours":
                    self.interval_seconds = 21600
                elif self.schedule_type == "weekly":
                    self.interval_seconds = 604800
                elif self.schedule_type == "custom":
                    self.interval_seconds = int(sched.get("interval_seconds", 3600))
                else:
                    self.interval_seconds = 86400
            except Exception as e:
                logger.warning(f"Could not load scheduler.yaml: {e}")

    def add_job(self, name: str, callback: callable) -> None:
        """Registers a background execution task job."""
        job = ScheduledJob(
            name=name,
            callback=callback,
            interval_seconds=self.interval_seconds,
        )
        self.jobs.append(job)
        logger.info(f"Registered scheduled job '{name}' (Type: {self.schedule_type}, Interval: {self.interval_seconds}s)")

    def start(self) -> None:
        """Starts background daemon scheduler loop execution thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("SchedulerService background daemon thread started.")

    def stop(self) -> None:
        """Signals stop event and joins background thread."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("SchedulerService stopped.")

    def _run_loop(self) -> None:
        """Internal daemon loop check."""
        while not self._stop_event.is_set():
            now = time.time()
            for job in self.jobs:
                if job.should_run(now):
                    try:
                        logger.info(f"Triggering scheduled job execution: '{job.name}'...")
                        job.execute()
                    except Exception as e:
                        logger.error(f"Error executing job '{job.name}': {e}", exc_info=True)
            # Sleep in tiny increments checking stop event
            if self._stop_event.wait(timeout=0.1):
                break

    def get_status(self) -> Dict[str, Any]:
        """Returns scheduler state parameters."""
        return {
            "running": self._running,
            "job_count": len(self.jobs),
            "schedule_type": self.schedule_type,
            "interval_seconds": self.interval_seconds,
        }
