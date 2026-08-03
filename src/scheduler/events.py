"""
Event Hooks and Event Bus for CyberScout AI Scheduler.

Enables pub/sub lifecycle notification hooks without modifying core scheduler logic.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from src.core.logging import get_logger

logger = get_logger(__name__)


class LifecycleEvent(str, Enum):
    """Authoritative lifecycle event types."""

    APP_STARTING = "app_starting"
    APP_READY = "app_ready"
    JOB_STARTING = "job_starting"
    JOB_FINISHED = "job_finished"
    JOB_SUCCESS = "job_success"
    JOB_FAILURE = "job_failure"
    APP_SHUTDOWN = "app_shutdown"

    def __str__(self) -> str:
        return self.value


EventCallback = Callable[[str, Optional[Dict[str, Any]]], None]


class EventBus:
    """
    Centralized event dispatcher for application lifecycle and job execution hooks.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[EventCallback]] = {}

    def subscribe(self, event: str, callback: EventCallback) -> None:
        """
        Subscribes a callback function to an event.

        Args:
            event: Event string or LifecycleEvent value.
            callback: Callable function taking (event_name, data_dict).
        """
        event_key = str(event)
        if event_key not in self._subscribers:
            self._subscribers[event_key] = []
        if callback not in self._subscribers[event_key]:
            self._subscribers[event_key].append(callback)
            logger.debug(f"Subscribed callback to event '{event_key}'.")

    def unsubscribe(self, event: str, callback: EventCallback) -> None:
        """Unsubscribes a callback function from an event."""
        event_key = str(event)
        if event_key in self._subscribers and callback in self._subscribers[event_key]:
            self._subscribers[event_key].remove(callback)

    def publish(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Publishes an event to all subscribed callbacks.

        Args:
            event: Event string or LifecycleEvent value.
            data: Optional payload dictionary.
        """
        event_key = str(event)
        callbacks = self._subscribers.get(event_key, [])
        logger.debug(f"Publishing event '{event_key}' to {len(callbacks)} subscribers.")
        for cb in callbacks:
            try:
                cb(event_key, data)
            except Exception as e:
                logger.error(f"Error in event callback for '{event_key}': {e}", exc_info=True)


# Global singleton instance
event_bus = EventBus()
