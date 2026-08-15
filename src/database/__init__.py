"""
Database & Knowledge Base Package for CyberScout AI.
"""

from src.database.admin_repository import AdminRepository
from src.database.analytics import AnalyticsEngine
from src.database.archive import ArchiveManager
from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.exceptions import KnowledgeError, RetentionError
from src.database.history_manager import HistoryManager
from src.database.history_repository import EmailHistoryRepository, SearchHistoryRepository
from src.database.interfaces import (
    IKeywordRepository,
    IOpportunityRepository,
    IPreferencesRepository,
    ISourceRepository,
    IStatisticsRepository,
)
from src.database.keyword_repository import KeywordRepository
from src.database.knowledge_manager import KnowledgeManager
from src.database.migrations import MigrationManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.provider_statistics import ProviderStatisticsTracker
from src.database.reporting import ReportGenerator
from src.database.retention import RetentionPolicyManager
from src.database.search_history import SearchHistoryTracker
from src.database.scheduler_repository import SchedulerRepository
from src.database.seed import SeedManager
from src.database.source_repository import SourceRepository
from src.database.stats_repository import PreferencesRepository, StatisticsRepository
from src.database.statistics_manager import StatisticsManager
from src.database.trend_engine import TrendEngine
from src.database.user_repository import UserRepository

__all__ = [
    "DatabaseManager",
    "BaseRepository",
    "UserRepository",
    "AdminRepository",
    "OpportunityRepository",
    "SourceRepository",
    "KeywordRepository",
    "SearchHistoryRepository",
    "EmailHistoryRepository",
    "StatisticsRepository",
    "PreferencesRepository",
    "SchedulerRepository",
    "MigrationManager",
    "SeedManager",
    # Interfaces
    "IOpportunityRepository",
    "ISourceRepository",
    "IKeywordRepository",
    "IStatisticsRepository",
    "IPreferencesRepository",
    # Phase 6 Knowledge Base
    "KnowledgeManager",
    "HistoryManager",
    "StatisticsManager",
    "SearchHistoryTracker",
    "ProviderStatisticsTracker",
    "TrendEngine",
    "AnalyticsEngine",
    "ArchiveManager",
    "RetentionPolicyManager",
    "ReportGenerator",
    "KnowledgeError",
    "RetentionError",
]
