"""
Retry Policy Manager for CyberScout AI Collection Framework.
"""

import time
from typing import Any, Callable, List, Optional, Tuple, Type
from src.core.logging import get_logger

logger = get_logger(__name__)


class CollectorRetry:
    """
    Executes network calls with configurable exponential backoff and retry rules.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        retryable_status_codes: Optional[List[int]] = None,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.retryable_status_codes = retryable_status_codes or [429, 500, 502, 503, 504]

    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Executes function with retry rules.

        Args:
            func: Target function to execute.

        Returns:
            Return value of function call.
        """
        delay = self.initial_delay
        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.max_attempts:
                    logger.error(f"Execution failed after {self.max_attempts} attempts: {e}")
                    raise
                logger.warning(
                    f"Attempt {attempt}/{self.max_attempts} failed ({e}). Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= self.backoff_factor

        if last_exception:
            raise last_exception
