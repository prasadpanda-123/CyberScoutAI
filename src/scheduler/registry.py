"""
Job Registry for CyberScout AI.

Manages automatic registration, enabling, disabling, and discovery of jobs.
"""

from typing import Dict, List, Optional
from src.scheduler.base_job import BaseJob
from src.core.exceptions import SchedulerError
from src.core.logging import get_logger

logger = get_logger(__name__)


class JobRegistry:
    """
    Centralized registry of pluggable system jobs.
    """

    def __init__(self):
        self._jobs: Dict[str, BaseJob] = {}
        self._enabled_status: Dict[str, bool] = {}

    def register(self, job: BaseJob, enabled: bool = True) -> bool:
        """
        Registers a job instance in the registry.

        Args:
            job: Concrete BaseJob instance.
            enabled: Initial enabled state.

        Returns:
            True if registered, False if duplicate.
        """
        if not isinstance(job, BaseJob):
            raise SchedulerError(f"Target job must inherit from BaseJob, got {type(job).__name__}.")

        job_id = job.job_id
        if job_id in self._jobs:
            logger.warning(f"Job ID '{job_id}' is already registered. Overwriting...")

        self._jobs[job_id] = job
        self._enabled_status[job_id] = enabled
        logger.info(f"Registered job '{job.job_name}' (ID: {job_id}).")
        return True

    def unregister(self, job_id: str) -> bool:
        """Unregisters a job by ID."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._enabled_status.pop(job_id, None)
            logger.info(f"Unregistered job ID '{job_id}'.")
            return True
        return False

    def get_job(self, job_id: str) -> Optional[BaseJob]:
        """Retrieves a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[BaseJob]:
        """Returns list of all registered jobs."""
        return list(self._jobs.values())

    def enable_job(self, job_id: str) -> None:
        """Enables job execution for a registered job."""
        if job_id in self._jobs:
            self._enabled_status[job_id] = True

    def disable_job(self, job_id: str) -> None:
        """Disables job execution for a registered job."""
        if job_id in self._jobs:
            self._enabled_status[job_id] = False

    def is_enabled(self, job_id: str) -> bool:
        """Returns True if job is enabled."""
        return self._enabled_status.get(job_id, False)
