"""
Abstract Base Job Interface for CyberScout AI.

All scheduled system tasks and pipeline jobs must implement this contract.
"""

from abc import ABC, abstractmethod


class BaseJob(ABC):
    """
    Abstract Base Class defining the contract for all scheduled jobs.
    """

    @property
    @abstractmethod
    def job_id(self) -> str:
        """Unique string identifier for the job."""
        pass

    @property
    @abstractmethod
    def job_name(self) -> str:
        """Human-readable display name for the job."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """
        Validates prerequisites before execution.

        Returns:
            True if ready to execute, False otherwise.
        """
        pass

    @abstractmethod
    def execute(self) -> bool:
        """
        Executes the main job business logic.

        Returns:
            True if job completed successfully, False on failure.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """
        Performs post-execution teardown or resource cleanup.
        """
        pass
