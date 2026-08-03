"""
Abstract Base Collector Contract for CyberScout AI Collection Framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.collectors.result import CollectorResult
from src.intelligence.planner_models import SearchTask


class BaseCollector(ABC):
    """
    Abstract Base Class for all CyberScout AI collectors.
    """

    def __init__(self, source_id: str):
        self.source_id = source_id
        self.is_initialized = False

    @property
    @abstractmethod
    def collector_name(self) -> str:
        """Human-readable display name for the collector."""
        pass

    def initialize(self) -> None:
        """Initializes collector resources (HTTP client, session, dependencies)."""
        self.is_initialized = True

    @abstractmethod
    def collect(self, task: SearchTask) -> CollectorResult:
        """
        Executes raw data collection for a planned SearchTask.

        Args:
            task: Validated SearchTask instance emitted by Phase 2 SearchPlanner.

        Returns:
            Standardized CollectorResult instance.
        """
        pass

    def validate(self, raw_data: Any) -> bool:
        """
        Validates raw collected payload before parsing.

        Returns:
            True if valid, False otherwise.
        """
        return raw_data is not None

    def normalize(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes raw item dictionary into canonical Opportunity schema fields.

        Args:
            raw_item: Individual item dictionary.

        Returns:
            Normalized item dictionary.
        """
        return raw_item

    def shutdown(self) -> None:
        """Cleans up collector resources on completion or application shutdown."""
        self.is_initialized = False
