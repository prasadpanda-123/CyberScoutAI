"""
Graceful shutdown signal handling utilities for CyberScout AI.
"""

import signal
from typing import Callable, List

from src.core.logging import get_logger

logger = get_logger(__name__)


class ShutdownHandler:
    """
    Registers SIGINT/SIGTERM handlers and runs cleanup routines.
    """

    def __init__(self):
        self.callbacks: List[Callable[[], None]] = []
        self._registered = False

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Adds a cleanup routine callback."""
        self.callbacks.append(callback)
        if not self._registered:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
            self._registered = True

    def _handle_signal(self, signum: int, frame) -> None:
        """Signal trigger logic."""
        logger.info(f"Signal {signum} caught. Starting graceful shutdown cleanup...")
        for cb in self.callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"Shutdown callback error: {e}")
        # Terminate process safely
        import sys
        sys.exit(0)
