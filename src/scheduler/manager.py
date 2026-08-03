"""
Scheduler Manager and Orchestrator for CyberScout AI.

Handles job registration, execution lifecycle, event hooks, health tracking,
configuration loading, and graceful shutdown handling.
"""

import signal
import sys
import time
from typing import Any, Dict, List, Optional

from src.core.config import config
from src.core.exceptions import SchedulerError
from src.core.logging import get_logger
from src.scheduler.base_job import BaseJob
from src.scheduler.events import LifecycleEvent, event_bus
from src.scheduler.health import JobMetrics
from src.scheduler.registry import JobRegistry
from src.scheduler.retry import retry_with_backoff

logger = get_logger(__name__)


class SchedulerManager:
    """
    Central Orchestrator managing scheduled jobs and application lifecycle events.
    """

    def __init__(
        self,
        registry: Optional[JobRegistry] = None,
        schedule_config: Optional[Dict[str, Any]] = None,
    ):
        self.registry = registry or JobRegistry()
        self.schedule_config = schedule_config or config.get("schedule", {})
        self.metrics: Dict[str, JobMetrics] = {}
        self.is_running = False
        self._paused_jobs: Dict[str, bool] = {}

        # Register signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Configures OS signal handlers for graceful termination."""
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, AttributeError):
            # Signal handling may not be supported in non-main threads or some platform configurations
            pass

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handles termination signals cleanly."""
        sig_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        logger.info(f"Received termination signal ({sig_name}). Initiating shutdown...")
        self.shutdown()
        sys.exit(0)

    def register_job(self, job: BaseJob, enabled: bool = True) -> bool:
        """Registers a job and initializes its metrics tracking."""
        success = self.registry.register(job, enabled=enabled)
        if success:
            self.metrics[job.job_id] = JobMetrics(job_id=job.job_id)
        return success

    def run_job(self, job_id: str) -> bool:
        """
        Executes a single job by ID with lifecycle event hooks and retry logic.

        Args:
            job_id: ID of the job to execute.

        Returns:
            True if job executed successfully, False otherwise.
        """
        job = self.registry.get_job(job_id)
        if not job:
            raise SchedulerError(f"Job ID '{job_id}' is not registered.")

        if not self.registry.is_enabled(job_id) or self.is_paused(job_id):
            logger.info(f"Skipping job '{job.job_name}' (disabled or paused).")
            return False

        metrics = self.metrics.setdefault(job_id, JobMetrics(job_id=job_id))
        metrics.status = "running"

        # Fire pre-execution lifecycle hook
        event_bus.publish(
            LifecycleEvent.JOB_STARTING,
            {"job_id": job_id, "job_name": job.job_name},
        )

        start_time = time.time()
        success = False
        error_msg = None

        try:
            # 1. Validate job prerequisites
            if not job.validate():
                raise SchedulerError(f"Job validation failed for '{job.job_name}'.")

            # 2. Execute job business logic
            max_retries = int(self.schedule_config.get("max_retries", 3))
            retry_delay = float(self.schedule_config.get("retry_delay_seconds", 1.0))

            @retry_with_backoff(max_retries=max_retries, initial_delay=retry_delay)
            def _execute_with_retry():
                return job.execute()

            success = _execute_with_retry()

            # 3. Teardown & Cleanup
            job.cleanup()

            duration = time.time() - start_time
            if success:
                metrics.record_success(duration)
                logger.info(f"Job '{job.job_name}' finished successfully in {duration:.2f}s.")
                event_bus.publish(
                    LifecycleEvent.JOB_SUCCESS,
                    {"job_id": job_id, "duration": duration},
                )
            else:
                error_msg = "Job execution returned False"
                metrics.record_failure(duration, error_msg)
                logger.warning(f"Job '{job.job_name}' completed with failure status.")
                event_bus.publish(
                    LifecycleEvent.JOB_FAILURE,
                    {"job_id": job_id, "error": error_msg},
                )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            metrics.record_failure(duration, error_msg)
            logger.error(f"Job '{job.job_name}' execution failed: {e}", exc_info=True)
            event_bus.publish(
                LifecycleEvent.JOB_FAILURE,
                {"job_id": job_id, "error": error_msg},
            )
            try:
                job.cleanup()
            except Exception:
                pass
        finally:
            event_bus.publish(
                LifecycleEvent.JOB_FINISHED,
                {"job_id": job_id, "success": success},
            )

        return success

    def run_all_jobs(self) -> Dict[str, bool]:
        """
        Executes all registered enabled jobs in sequence.

        Returns:
            Dictionary of job_id -> execution_success_bool.
        """
        self.is_running = True
        results = {}

        event_bus.publish(LifecycleEvent.APP_STARTING, {"status": "starting"})
        event_bus.publish(LifecycleEvent.APP_READY, {"status": "ready"})

        for job in self.registry.list_jobs():
            if self.registry.is_enabled(job.job_id):
                results[job.job_id] = self.run_job(job.job_id)

        self.is_running = False
        return results

    def pause_job(self, job_id: str) -> None:
        """Pauses execution for a specific job."""
        self._paused_jobs[job_id] = True
        if job_id in self.metrics:
            self.metrics[job_id].status = "paused"
        logger.info(f"Job ID '{job_id}' paused.")

    def resume_job(self, job_id: str) -> None:
        """Resumes execution for a paused job."""
        self._paused_jobs.pop(job_id, None)
        if job_id in self.metrics:
            self.metrics[job_id].status = "pending"
        logger.info(f"Job ID '{job_id}' resumed.")

    def is_paused(self, job_id: str) -> bool:
        """Returns True if job is currently paused."""
        return self._paused_jobs.get(job_id, False)

    def get_job_metrics(self, job_id: str) -> Optional[JobMetrics]:
        """Retrieves metrics object for a job."""
        return self.metrics.get(job_id)

    def shutdown(self) -> None:
        """Performs graceful shutdown of scheduler and fires event hooks."""
        logger.info("Executing SchedulerManager shutdown sequence...")
        event_bus.publish(LifecycleEvent.APP_SHUTDOWN, {"status": "shutdown"})
        self.is_running = False
        logger.info("SchedulerManager shutdown complete.")
