"""
Runtime State Definitions for CyberScout AI.
"""

from enum import Enum


class RuntimeState(Enum):
    """Represents current execution status of autonomous system."""

    IDLE = "Idle"
    RUNNING = "Running"
    SLEEPING = "Sleeping"
    STOPPING = "Stopping"
    STOPPED = "Stopped"
    ERROR = "Error"
