"""
Repository Interfaces for CyberScout AI.

Defines Data Access Object (DAO) contracts for database operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.models.keyword import Keyword
from src.models.opportunity import Opportunity
from src.models.source import Source
from src.models.stats import ApplicationStatistics, Preferences


class IOpportunityRepository(ABC):
    """Repository contract for Opportunity persistence and queries."""

    @abstractmethod
    def upsert(self, opp: Opportunity) -> str:
        """Persists or updates an opportunity."""
        pass

    @abstractmethod
    def get_by_id(self, opp_id: str) -> Optional[Opportunity]:
        """Retrieves opportunity by ID."""
        pass

    @abstractmethod
    def get_by_url_hash(self, url_hash: str) -> Optional[Opportunity]:
        """Retrieves opportunity by SHA-256 URL hash."""
        pass

    @abstractmethod
    def get_active_opportunities(
        self, limit: int = 50, category: Optional[str] = None
    ) -> List[Opportunity]:
        """Retrieves active opportunities ordered by score."""
        pass

    @abstractmethod
    def mark_as_duplicate(self, opp_id: str, canonical_id: str) -> None:
        """Links a duplicate opportunity to canonical record."""
        pass

    @abstractmethod
    def update_status(self, opp_id: str, new_status: str) -> None:
        """Updates opportunity lifecycle status."""
        pass


class ISourceRepository(ABC):
    """Repository contract for Source persistence and queries."""

    @abstractmethod
    def sync_from_config(self, sources_config: dict) -> int:
        """Syncs configuration sources into database."""
        pass

    @abstractmethod
    def get_active_sources(self) -> List[Source]:
        """Retrieves enabled sources."""
        pass

    @abstractmethod
    def get_sources_by_method(self, method: str) -> List[Source]:
        """Retrieves sources matching collection method."""
        pass


class IKeywordRepository(ABC):
    """Repository contract for Keyword taxonomy terms."""

    @abstractmethod
    def save_keyword(self, keyword: Keyword) -> str:
        """Saves a keyword taxonomy record."""
        pass

    @abstractmethod
    def get_keywords_by_domain(self, domain: str) -> List[Keyword]:
        """Retrieves taxonomy keywords for a domain."""
        pass


class IStatisticsRepository(ABC):
    """Repository contract for system operational metrics."""

    @abstractmethod
    def record_statistics(self, stats: ApplicationStatistics) -> str:
        """Records daily/source statistics."""
        pass

    @abstractmethod
    def get_statistics_by_date(self, date_str: str) -> List[ApplicationStatistics]:
        """Retrieves statistics for a specific date."""
        pass


class IPreferencesRepository(ABC):
    """Repository contract for user preferences."""

    @abstractmethod
    def set_preference(self, key: str, value: str) -> None:
        """Sets a user preference key-value pair."""
        pass

    @abstractmethod
    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves a user preference value."""
        pass
