"""
Retry logic and decorators for SMTP transmission.
"""

import time
from typing import Callable, Type, Union

from src.notifier.exceptions import RetryExceeded


def retry_smtp(attempts: int = 3, delay_secs: float = 1.0, exceptions_to_catch: Union[Type[Exception], tuple] = Exception):
    """
    Decorator for retrying SMTP delivery operations using exponential backoff.
    """

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            current_delay = delay_secs
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions_to_catch as e:
                    if attempt == attempts:
                        raise RetryExceeded(f"All {attempts} SMTP retry attempts failed: {e}", original_exception=e)
                    time.sleep(current_delay)
                    current_delay *= 2.0
            return None

        return wrapper

    return decorator
