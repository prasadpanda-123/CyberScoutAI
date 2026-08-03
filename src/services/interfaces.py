"""
Service Interfaces for CyberScout AI.

Defines high-level domain service contracts.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.models.opportunity import Opportunity
from src.models.search_models import SearchQuery, SearchResult


class ICollectorService(ABC):
    """Contract for data collection service orchestration."""

    @abstractmethod
    def run_collectors(self, sources: Optional[List[str]] = None) -> List[SearchResult]:
        """Runs configured data collectors."""
        pass


class IProcessorService(ABC):
    """Contract for opportunity transformation and pipeline execution."""

    @abstractmethod
    def process_pipeline(
        self, raw_results: List[SearchResult]
    ) -> List[Opportunity]:
        """Executes full validation, cleaning, normalization, dedup, and ranking."""
        pass


class INotificationService(ABC):
    """Contract for email rendering and delivery."""

    @abstractmethod
    def send_digest(self, opportunities: List[Opportunity]) -> bool:
        """Renders and transmits HTML digest email."""
        pass


class ISearchService(ABC):
    """Contract for Search Intelligence query generation."""

    @abstractmethod
    def generate_search_queries(self) -> List[SearchQuery]:
        """Generates target search queries from taxonomy and sources."""
        pass


class IDatabaseService(ABC):
    """Contract for database connection and schema management."""

    @abstractmethod
    def initialize(self) -> None:
        """Initializes database schema and connections."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Performs database health ping."""
        pass


class IConfigurationService(ABC):
    """Contract for application configuration management."""

    @abstractmethod
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves configuration value by key."""
        pass
