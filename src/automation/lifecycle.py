"""
Lifecycle events manager for automation engine using existing EventBus.
"""

from typing import Any, Dict, Optional

from src.scheduler.events import LifecycleEvent, event_bus


class LifecyclePublisher:
    """
    Publishes lifecycle state change events to EventBus.
    """

    def publish_event(self, event_type: str, message: str, run_id: Optional[str] = None) -> None:
        """
        Publishes a lifecycle event as a plain dict payload.

        Args:
            event_type: Name string of event.
            message: Accompanying description text.
            run_id: Execution run identifier.
        """
        payload: Dict[str, Any] = {"message": message}
        if run_id:
            payload["run_id"] = run_id

        # Map known types to LifecycleEvent enum values; fall back to raw string
        event_map = {
            "Pipeline Started": LifecycleEvent.APP_STARTING,
            "Pipeline Finished": LifecycleEvent.APP_SHUTDOWN,
            "Collection Started": LifecycleEvent.JOB_STARTING,
            "Collection Completed": LifecycleEvent.JOB_SUCCESS,
            "Pipeline Failed": LifecycleEvent.JOB_FAILURE,
        }
        event_key = str(event_map.get(event_type, event_type))
        event_bus.publish(event_key, payload)
