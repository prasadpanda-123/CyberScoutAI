"""
Automation and Orchestration package for CyberScout AI.
"""

from src.automation.engine import AutomationEngine
from src.automation.exceptions import (
    AutomationError,
    SchedulerError,
    PipelineRunnerError,
)
from src.automation.jobs import ScheduledJob
from src.automation.lifecycle import LifecyclePublisher
from src.automation.metrics import RunMetrics
from src.automation.pipeline import PipelineRunner
from src.automation.scheduler import SchedulerService
from src.automation.state import RuntimeState
from src.automation.runtime import ShutdownHandler

__all__ = [
    "AutomationEngine",
    "PipelineRunner",
    "SchedulerService",
    "ScheduledJob",
    "LifecyclePublisher",
    "RunMetrics",
    "RuntimeState",
    "ShutdownHandler",
    # Exceptions
    "AutomationError",
    "SchedulerError",
    "PipelineRunnerError",
]
