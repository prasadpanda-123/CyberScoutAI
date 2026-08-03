"""
Database package for CyberScout AI.
"""

from src.database.backup import BackupManager
from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.history_repository import EmailHistoryRepository, SearchHistoryRepository
from src.database.interfaces import (
    IKeywordRepository,
    IOpportunityRepository,
    IPreferencesRepository,
    ISourceRepository,
    IStatisticsRepository,
)
from src.database.keyword_repository import KeywordRepository
from src.database.migrations import MigrationManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.seed import SeedManager
from src.database.source_repository import SourceRepository
from src.database.stats_repository import PreferencesRepository, StatisticsRepository

__all__ = [
    # Infrastructure
    "DatabaseManager",
    "BaseRepository",
    "MigrationManager",
    "SeedManager",
    "BackupManager",
    # Concrete Repositories
    "OpportunityRepository",
    "SourceRepository",
    "KeywordRepository",
    "SearchHistoryRepository",
    "EmailHistoryRepository",
    "StatisticsRepository",
    "PreferencesRepository",
    # Interfaces
    "IOpportunityRepository",
    "ISourceRepository",
    "IKeywordRepository",
    "IStatisticsRepository",
    "IPreferencesRepository",
]
