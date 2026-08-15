"""
Authoritative Opportunity Data Model.

The Opportunity model is the single source of truth across collectors,
processors, database storage, ranking engine, and email notifier.
Reference: docs/architecture/data_model.md
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
import uuid

from src.models.enums import Difficulty, OpportunityCategory, Status


@dataclass
class Opportunity:
    """
    Canonical Opportunity model representing a single cybersecurity opportunity item.
    """

    title: str
    url: str
    source_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: Optional[str] = None
    category: str = OpportunityCategory.OTHER.value
    provider: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    remote: bool = False
    paid: Optional[bool] = None
    certificate: bool = False
    price_raw: Optional[str] = None
    price_normalized: Optional[str] = None
    currency: Optional[str] = None
    deadline: Optional[str] = None
    published_date: Optional[str] = None
    discovered_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    duration: Optional[str] = None
    difficulty: str = Difficulty.UNKNOWN.value
    tags: List[str] = field(default_factory=list)
    beginner_friendly: Optional[bool] = None
    score: int = 0
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    quality_score: float = 0.0
    is_rejected: bool = False
    rejection_reason: str = ""
    quality_flags: str = ""
    topic_score: float = 0.0
    keyword_score: float = 0.0
    spam_score: float = 0.0
    freshness_score: float = 100.0
    provider_score: float = 100.0
    link_status: str = "valid"
    verification_status: str = "verified"
    last_verified: Optional[str] = None
    expired: int = 0
    archived: int = 0
    status: str = Status.ACTIVE.value
    duplicate_of_id: Optional[str] = None
    run_id: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    last_seen: Optional[str] = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def generate_url_hash(self) -> str:
        """
        Computes a canonical SHA-256 hash of the normalized URL for fast dedup lookups.

        Returns:
            64-character hexadecimal SHA-256 string.
        """
        from src.utils.url_utils import normalize_url
        canonical_url = normalize_url(self.url)
        return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Converts Opportunity instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Opportunity":
        """
        Constructs an Opportunity instance from a dictionary, safely filtering
        unexpected keys.
        """
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
