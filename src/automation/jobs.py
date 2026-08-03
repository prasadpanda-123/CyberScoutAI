"""
Job abstractions for scheduled runs of CyberScout AI.
"""

from typing import Any, Callable, Optional


class ScheduledJob:
    """
    Job container defining task trigger intervals.
    """

    def __init__(self, name: str, callback: Callable[[], Any], interval_seconds: int):
        self.name = name
        self.callback = callback
        self.interval_seconds = interval_seconds
        self.last_run: Optional[float] = None

    def should_run(self, current_time: float) -> bool:
        """Determines if the job interval elapsed."""
        if self.last_run is None:
            return True
        return (current_time - self.last_run) >= self.interval_seconds

    def execute(self) -> Any:
        """Executes the task callback."""
        import time
        self.last_run = time.time()
        return self.callback()
