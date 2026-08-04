"""
Exceptions for the Automation and Scheduler Subsystem of CyberScout AI.
"""

from src.core.exceptions import CyberScoutError


class AutomationError(CyberScoutError):
    """Base exception class for all Automation Engine errors."""

    pass


class SchedulerError(AutomationError):
    """Raised when scheduling jobs or scheduler service operations fail."""

    pass


class PipelineRunnerError(AutomationError):
    """Raised when running the automated search and collection pipeline fails."""

    pass
