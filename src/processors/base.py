"""
Abstract Processor Interfaces for CyberScout AI.

Defines processing pipeline contracts per docs/architecture/processor_contract.md.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

from src.models.opportunity import Opportunity


class BaseProcessor(ABC):
    """
    Abstract Base Class for all pipeline processors.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the processing stage."""
        pass

    @abstractmethod
    def process(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """
        Transforms or filters a list of Opportunity items.

        Args:
            opportunities: Input list of Opportunity objects.

        Returns:
            Transformed list of Opportunity objects.
        """
        pass


class ICleaner(BaseProcessor):
    """Interface for text and HTML cleaning stage."""

    @abstractmethod
    def clean(self, opp: Opportunity) -> Opportunity:
        """Cleans title, description, and raw text fields."""
        pass


class IValidator(BaseProcessor):
    """Interface for field validation and quality control stage."""

    @abstractmethod
    def validate(self, opp: Opportunity) -> Tuple[bool, List[str]]:
        """
        Validates opportunity fields.

        Returns:
            Tuple of (is_valid, list_of_error_strings).
        """
        pass


class INormalizer(BaseProcessor):
    """Interface for standardizing dates, locations, prices, and modes."""

    @abstractmethod
    def normalize(self, opp: Opportunity) -> Opportunity:
        """Normalizes dates, price, remote flag, and difficulty."""
        pass


class ICategorizer(BaseProcessor):
    """Interface for taxonomy classification and tag assignment."""

    @abstractmethod
    def categorize(self, opp: Opportunity) -> Opportunity:
        """Assigns canonical OpportunityCategory and taxonomy tags."""
        pass


class IDuplicateDetector(BaseProcessor):
    """Interface for identifying duplicate opportunities."""

    @abstractmethod
    def find_duplicates(
        self, candidates: List[Opportunity]
    ) -> List[Tuple[Opportunity, Opportunity]]:
        """
        Identifies duplicate pairs among opportunity candidates.

        Returns:
            List of (canonical_opp, duplicate_opp) tuples.
        """
        pass


class IRankingProcessor(BaseProcessor):
    """Interface for scoring and ranking opportunities."""

    @abstractmethod
    def compute_score(self, opp: Opportunity) -> Opportunity:
        """Computes ranking score and score breakdown."""
        pass


class IStorageProcessor(BaseProcessor):
    """Interface for database persistence stage."""

    @abstractmethod
    def store(self, opportunities: List[Opportunity]) -> int:
        """
        Persists processed opportunities into SQLite.

        Returns:
            Count of stored/updated records.
        """
        pass
