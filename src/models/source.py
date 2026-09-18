"""
Source Data Model for CyberScout AI.

Represents a target internet intelligence source.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from src.models.enums import CollectionMethod, SourceStatus, OpportunityCategory


@dataclass
class Source:
    """
    Model representing a registered opportunity data source.
    """

    id: str
    name: str
    collection_method: str = CollectionMethod.RSS.value
    default_category: str = OpportunityCategory.OTHER.value
    status: str = SourceStatus.ACTIVE.value
    enabled: bool = True
    official: bool = False
    trust_score: float = 1.0
    maintenance_level: str = "stable"
    update_frequency: str = "daily"
    max_requests_per_run: int = 10
    request_delay_ms: int = 1000

    # Phase 2 Canonical Registry & Health Extensions
    canonical_url: Optional[str] = None
    organization: Optional[str] = None
    country_scope: str = "GLOBAL"
    language: str = "en"
    source_family: str = "other"
    opportunity_types: list = None
    collector_type: str = "rss"
    access_method: str = "rss"
    trust_tier: str = "tier_2"
    requires_auth: bool = False
    rate_limit_policy: dict = None
    robots_policy: str = "respect"
    terms_review_status: str = "pending_review"
    parser_version: str = "1.0.0"
    health_status: str = "healthy"
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_item_count: int = 0
    last_new_item_count: int = 0
    last_updated_item_count: int = 0
    failure_count: int = 0
    success_count: int = 0
    latency: float = 0.0
    error_class: Optional[str] = None

    def __post_init__(self):
        if self.opportunity_types is None:
            self.opportunity_types = []
        if self.rate_limit_policy is None:
            self.rate_limit_policy = {}

    def to_dict(self) -> Dict[str, Any]:
        """Converts Source instance to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Source":
        """Reconstructs Source instance from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
