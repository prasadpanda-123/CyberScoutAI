"""
Abstract Base Collector Interface for CyberScout AI.

All concrete source collectors must implement this interface.
Reference: docs/architecture/collector_contract.md
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.models.opportunity import Opportunity
from src.models.search_models import SearchQuery, SearchResult


class BaseCollector(ABC):
    """
    Abstract Base Class defining the contract for all CyberScout collectors.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier of the target collector source."""
        pass

    @property
    @abstractmethod
    def collection_method(self) -> str:
        """Ingestion protocol/type (rss, api, html, playwright)."""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validates required configuration parameters for the collector.

        Returns:
            True if configuration is valid, False otherwise.
        """
        pass

    @abstractmethod
    def collect(self, query: Optional[SearchQuery] = None) -> SearchResult:
        """
        Executes raw opportunity discovery and extraction for the source.

        Args:
            query: Optional SearchQuery target.

        Returns:
            SearchResult containing raw fetched items and execution status.
        """
        pass

    @abstractmethod
    def parse_to_opportunities(self, result: SearchResult) -> List[Opportunity]:
        """
        Parses raw extracted items into canonical Opportunity model instances.

        Args:
            result: SearchResult object containing raw items.

        Returns:
            List of standardized Opportunity objects.
        """
        pass
