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
    opportunity_type: Optional[str] = None
    pricing_type: str = "unknown"
    price_amount: Optional[float] = None
    application_fee: Optional[float] = None
    certificate_fee: Optional[float] = None
    is_free: Optional[bool] = None
    free_conditions: Optional[str] = None
    stipend_type: str = "none"
    stipend_amount: Optional[float] = None
    stipend_currency: Optional[str] = None
    certificate_available: str = "unknown"
    certificate_cost: str = "unknown"
    eligibility: Optional[str] = None
    requirements: Optional[str] = None
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
    # Phase 2.1 Layered Identity & Harvesting State
    source_external_id: Optional[str] = None
    canonical_url: Optional[str] = None
    identity_fingerprint: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    last_changed_at: Optional[str] = None
    last_harvested_at: Optional[str] = None
    # Phase 6 Industrial Data Quality & Lifecycle State
    lifecycle_status: str = "active"
    quality_status: str = "passed"
    completeness_score: float = 1.0
    quarantine_reason: Optional[str] = None
    stale_at: Optional[str] = None
    absence_count: int = 0

    def __post_init__(self):
        from src.utils.url_utils import normalize_url
        if not self.canonical_url and self.url:
            self.canonical_url = normalize_url(self.url)
        if not self.identity_fingerprint:
            self.identity_fingerprint = self.compute_identity_fingerprint()
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self.first_seen_at:
            self.first_seen_at = now_iso
        if not self.last_seen_at:
            self.last_seen_at = now_iso
        if not self.last_harvested_at:
            self.last_harvested_at = now_iso

    def compute_identity_fingerprint(self) -> str:
        """
        Computes a deterministic SHA-256 identity fingerprint of canonical content.
        Participating fields:
        - source_id (lowercased, stripped)
        - clean title (lowercased, collapsed whitespace)
        - clean provider/company (lowercased, stripped)
        - category (lowercased, stripped)
        - opportunity_type (lowercased, stripped)
        - clean description core (first 200 chars, stripped of HTML tags and extra whitespace)

        Volatile fields (timestamps, random IDs, URLs with tracking parameters, deadlines)
        are explicitly excluded so that content changes do not fracture opportunity identity.
        """
        import re
        sid = (self.source_id or "").strip().lower()
        clean_title = " ".join((self.title or "").strip().lower().split())
        clean_prov = " ".join((self.provider or self.company or "").strip().lower().split())
        cat = (self.category or "other").strip().lower()
        opp_type = (self.opportunity_type or "").strip().lower()

        raw_desc = self.description or ""
        desc_no_html = re.sub(r"<[^>]+>", " ", raw_desc)
        clean_desc_core = " ".join(desc_no_html.strip().lower().split())[:200]

        components = [sid, clean_title, clean_prov, cat, opp_type, clean_desc_core]
        canonical_str = "|".join(components)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def generate_url_hash(self) -> str:
        """
        Computes a canonical SHA-256 hash of the normalized URL for fast dedup lookups.

        Returns:
            64-character hexadecimal SHA-256 string.
        """
        from src.utils.url_utils import normalize_url
        target_url = self.canonical_url or self.url
        canonical_url = normalize_url(target_url)
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
