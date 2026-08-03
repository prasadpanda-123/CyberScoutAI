"""
Intelligence Abstract Interfaces for CyberScout AI.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.models.opportunity import Opportunity


class IRankingEngine(ABC):
    """
    Abstract contract for opportunity ranking engines.
    """

    @abstractmethod
    def rank_opportunity(self, opportunity: Opportunity) -> Opportunity:
        """Ranks and scores an Opportunity."""
        pass

    @abstractmethod
    def rank_batch(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """Ranks and sorts a batch of Opportunities."""
        pass
