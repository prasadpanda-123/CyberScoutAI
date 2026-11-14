"""
Discovery Domain Models and Enums for CyberScout AI.

Defines canonical data structures for global opportunity discovery via Tavily,
including query specifications, candidate models, and run summaries.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Any, Dict, List, Optional
import uuid


class OpportunityCategory(str, Enum):
    """Canonical taxonomy of cybersecurity opportunities."""

    INTERNSHIP = "internship"
    JOB = "job"
    BUG_BOUNTY = "bug_bounty"
    VULNERABILITY_DISCLOSURE = "vulnerability_disclosure"
    CTF = "ctf"
    HACKATHON = "hackathon"
    FREE_TRAINING = "free_training"
    COURSE_CERTIFICATION = "course_certification"
    SCHOLARSHIP = "scholarship"
    RESEARCH = "research"
    CONFERENCE = "conference"
    WORKSHOP_WEBINAR = "workshop_webinar"
    DFIR_CHALLENGE = "dfir_challenge"
    OPEN_SOURCE_PROGRAM = "open_source_program"
    SECURITY_MENTORSHIP = "security_mentorship"
    OTHER = "other"


class GeographicRegion(str, Enum):
    """Authoritative geographic target regions."""

    INDIA = "india"
    GLOBAL_REMOTE = "global_remote"
    NORTH_AMERICA = "north_america"
    SOUTH_AMERICA = "south_america"
    EUROPE = "europe"
    ASIA = "asia"
    AFRICA = "africa"
    MIDDLE_EAST = "middle_east"
    OCEANIA = "oceania"


class CandidateProcessingStatus(str, Enum):
    """Lifecycle state of a discovered opportunity candidate."""

    DISCOVERED = "discovered"
    DUPLICATE = "duplicate"
    SECURITY_REJECTED = "security_rejected"
    READY_FOR_EXTRACTION = "ready_for_extraction"
    QUARANTINED = "quarantined"


class ExtractionStatus(str, Enum):
    """Content extraction state for Firecrawl (Phase C)."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PricingVerificationStatus(str, Enum):
    """
    Economic status classification.
    Zero-trust rule: default is always UNCERTAIN until verified.
    """

    UNCERTAIN = "UNCERTAIN"
    VERIFIED_FREE = "VERIFIED_FREE"
    VERIFIED_PAID = "VERIFIED_PAID"


@dataclass
class SearchQuerySpec:
    """Specification for an individual search query executed by the discovery client."""

    query: str
    region: GeographicRegion
    category: OpportunityCategory
    target_platform: Optional[str] = None
    priority: int = 1  # 1 (Highest) to 5 (Lowest)
    include_domains: List[str] = field(default_factory=list)
    exclude_domains: List[str] = field(default_factory=list)
    search_depth: str = "advanced"
    max_results: int = 15

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "region": self.region.value,
            "category": self.category.value,
            "target_platform": self.target_platform,
            "priority": self.priority,
            "include_domains": self.include_domains,
            "exclude_domains": self.exclude_domains,
            "search_depth": self.search_depth,
            "max_results": self.max_results,
        }


@dataclass
class DiscoveredCandidate:
    """
    Staged candidate discovered via external search API before content extraction
    and verification. Preserves raw provenance and never pollutes verified Opportunities table.
    """

    discovery_run_id: str
    search_query: str
    search_provider: str
    original_url: str
    canonical_url: str
    url_hash: str
    title: str
    snippet: str
    source_domain: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    platform_name: Optional[str] = None
    country_or_scope: str = "Global"
    category: str = OpportunityCategory.OTHER.value
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    processing_status: str = CandidateProcessingStatus.DISCOVERED.value
    extraction_status: str = ExtractionStatus.PENDING.value
    pricing_verification_status: str = PricingVerificationStatus.UNCERTAIN.value
    is_free: Optional[bool] = None  # None by default; never assumed free without verification
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts candidate to a standard dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscoveredCandidate":
        """Constructs DiscoveredCandidate instance safely filtering unrecognized keys."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class DiscoveryBudget:
    """Configurable usage limits and cost guardrails for external search APIs."""

    daily_limit: int = 50
    monthly_budget: int = 1000
    max_searches_per_run: int = 25
    max_results_per_query: int = 15

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryRunSummary:
    """Summary metrics and audit record for an executed Tavily discovery run."""

    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    queries_planned: int = 0
    queries_executed: int = 0
    queries_failed: int = 0
    candidates_found_raw: int = 0
    candidates_valid: int = 0
    candidates_rejected_security: int = 0
    candidates_duplicates: int = 0
    candidates_staged: int = 0
    candidates_by_region: Dict[str, int] = field(default_factory=dict)
    candidates_by_category: Dict[str, int] = field(default_factory=dict)
    candidates_by_platform: Dict[str, int] = field(default_factory=dict)
    status: str = "completed"
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionBudget:
    """Configurable usage limits and rate controls for Firecrawl web scraper."""

    daily_limit: int = 100
    max_pages_per_run: int = 25
    max_response_size: int = 2097152   # 2 MB response size ceiling
    rate_limit_rpm: int = 10           # Max requests per minute
    timeout_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractedContentData:
    """
    Normalized opportunity fields and raw content extracted by Firecrawl.
    
    Derived strictly from page evidence without hallucination or invented facts.
    Missing fields remain None or explicitly unknown.
    """

    original_url: str
    canonical_url: str
    title: Optional[str] = None
    organization_or_publisher: Optional[str] = None
    main_content_markdown: Optional[str] = None
    main_content_html: Optional[str] = None
    short_description: Optional[str] = None
    opportunity_type: Optional[str] = None
    required_skills: List[str] = field(default_factory=list)
    eligibility_requirements: Optional[str] = None
    country_and_location: Optional[str] = None
    remote_or_onsite: Optional[str] = None  # 'remote', 'onsite', 'hybrid', or None
    publication_date: Optional[str] = None
    application_deadline: Optional[str] = None
    application_url: Optional[str] = None
    pricing_statements: Optional[str] = None
    currency: Optional[str] = None
    fee_amount: Optional[float] = None
    source_evidence: List[str] = field(default_factory=list)
    content_hash: str = ""
    extracted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extraction_status: str = ExtractionStatus.COMPLETED.value
    error_details: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedContentData":
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class ExtractionRunSummary:
    """Summary metrics and audit record for an executed Firecrawl extraction run."""

    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    pages_attempted: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    pages_rejected_security: int = 0
    pages_duplicate: int = 0
    pages_skipped: int = 0
    status: str = "completed"
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



