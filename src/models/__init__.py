"""
Models package for CyberScout AI.
"""

from src.models.enums import (
    CertificateType,
    CollectionMethod,
    DeliveryMode,
    Difficulty,
    EmploymentType,
    OpportunityCategory,
    OpportunityStatus,
    ProviderType,
    RankingReason,
    SourceStatus,
    SourceType,
    Status,
)
from src.models.keyword import Keyword
from src.models.opportunity import Opportunity
from src.models.search_models import SearchQuery, SearchResult
from src.models.source import Source
from src.models.stats import ApplicationStatistics, Preferences
from src.models.types import JsonDict, OpportunityId, RunId, ScoreBreakdown, SourceId, TagList

__all__ = [
    # Models
    "Opportunity",
    "Source",
    "Keyword",
    "SearchQuery",
    "SearchResult",
    "ApplicationStatistics",
    "Preferences",
    # Enums
    "OpportunityCategory",
    "SourceType",
    "SourceStatus",
    "Difficulty",
    "EmploymentType",
    "ProviderType",
    "CertificateType",
    "DeliveryMode",
    "CollectionMethod",
    "RankingReason",
    "Status",
    "OpportunityStatus",
    # Types
    "JsonDict",
    "OpportunityId",
    "SourceId",
    "RunId",
    "ScoreBreakdown",
    "TagList",
]
