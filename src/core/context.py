"""
Application Context Container for CyberScout AI.

Provides explicit dependency wiring and shared context for application layers
without global singleton abuse.
"""

from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional

from src.core.config import Config
from src.database.connection import DatabaseManager
from src.database.history_repository import EmailHistoryRepository, SearchHistoryRepository
from src.database.keyword_repository import KeywordRepository
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_repository import SourceRepository
from src.database.stats_repository import PreferencesRepository, StatisticsRepository
from src.scheduler.manager import SchedulerManager


@dataclass
class RepositoryContainer:
    """Container holding instantiated database repositories."""

    opportunities: OpportunityRepository
    sources: SourceRepository
    keywords: KeywordRepository
    search_history: SearchHistoryRepository
    email_history: EmailHistoryRepository
    statistics: StatisticsRepository
    preferences: PreferencesRepository

    @classmethod
    def create_all(cls, db_manager: DatabaseManager) -> "RepositoryContainer":
        """Instantiates all repository instances using provided DatabaseManager."""
        return cls(
            opportunities=OpportunityRepository(db_manager),
            sources=SourceRepository(db_manager),
            keywords=KeywordRepository(db_manager),
            search_history=SearchHistoryRepository(db_manager),
            email_history=EmailHistoryRepository(db_manager),
            statistics=StatisticsRepository(db_manager),
            preferences=PreferencesRepository(db_manager),
        )


class AppContext:
    """
    Central Application Context holding explicitly wired subsystem instances.
    """

    def __init__(
        self,
        config_instance: Config,
        logger_instance: logging.Logger,
        db_manager: DatabaseManager,
        repositories: RepositoryContainer,
        scheduler: SchedulerManager,
        services: Optional[Dict[str, Any]] = None,
    ):
        self.config = config_instance
        self.logger = logger_instance
        self.db_manager = db_manager
        self.repositories = repositories
        self.scheduler = scheduler
        self.services = services or {}
