"""
Retry and Backoff Framework for CyberScout AI.

Provides configurable retries with exponential backoff for jobs and network calls.
"""

import functools
import time
from typing import Any, Callable, Optional, Tuple, Type
from src.core.logging import get_logger

logger = get_logger(__name__)


def retry_with_backoff(
    func: Optional[Callable] = None,
    *,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator / Helper for retrying a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Delay in seconds before first retry.
        backoff_factor: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch and retry on.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = initial_delay
            last_exception: Optional[Exception] = None

            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"Execution of '{fn.__name__}' failed after {max_retries} attempts: {e}"
                        )
                        raise
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} for '{fn.__name__}' failed ({e}). Retrying in {current_delay:.1f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff_factor

            if last_exception:
                raise last_exception

        return wrapper

    if func is None:
        return decorator
    return decorator(func)
