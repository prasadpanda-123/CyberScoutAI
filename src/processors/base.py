"""
Abstract Base Processor Contract for CyberScout AI Processing Engine.
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.models.opportunity import Opportunity


class BaseProcessor(ABC):
    """
    Abstract Base Class for all pipeline processors.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @property
    @abstractmethod
    def processor_name(self) -> str:
        """Human-readable display name for the processor."""
        pass

    @abstractmethod
    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Processes an Opportunity sequentially.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Processed Opportunity instance, or None if rejected by pipeline.
        """
        pass


class ICleaner(ABC):
    """
    Abstract Interface for text cleaning operations.
    """

    @abstractmethod
    def clean(self, raw_text: str) -> str:
        """Cleans raw text string."""
        pass
