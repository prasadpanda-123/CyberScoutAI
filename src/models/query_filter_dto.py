"""
Phase 4 Query & Result Data Transfer Objects (DTOs).

Provides strict server-side validation, sanitization, allowlisting,
and pagination clamping for SSR-first opportunity discovery.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode


ALLOWED_SORTS = {"relevance", "newest", "deadline", "score", "recommended"}
ALLOWED_SORT_DIRS = {"asc", "desc"}
ALLOWED_PRICING_TYPES = {"free", "paid", "freemium", "unknown"}
ALLOWED_DIFFICULTIES = {"beginner", "intermediate", "advanced", "expert"}
ALLOWED_STIPEND_TYPES = {"unpaid", "paid", "performance_based", "expenses_covered"}
MAX_KEYWORD_LENGTH = 200
MAX_PER_PAGE = 200
DEFAULT_PER_PAGE = 24


def _parse_bool(val: Any) -> Optional[bool]:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def _sanitize_string(val: Optional[str], max_len: int = 200) -> Optional[str]:
    if val is None:
        return None
    # Strip null bytes and control chars
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", val).strip()
    if not clean:
        return None
    return clean[:max_len]


@dataclass
class QueryFilterDTO:
    """Validated, normalized search and filter parameters for opportunity queries."""

    keyword: Optional[str] = None
    category: Optional[str] = None
    opportunity_type: Optional[str] = None
    source_id: Optional[str] = None
    is_free: Optional[bool] = None
    pricing_type: Optional[str] = None
    stipend_type: Optional[str] = None
    remote: Optional[bool] = None
    difficulty: Optional[str] = None
    deadline: Optional[str] = None  # 'active', 'upcoming', 'past', or YYYY-MM-DD
    sort: str = "relevance"
    sort_dir: str = "desc"
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE
    saved_only: bool = False
    user_id: Optional[str] = None
    lifecycle_status: Optional[str] = None

    def __post_init__(self):
        if self.keyword is not None:
            stripped = self.keyword.strip()
            self.keyword = stripped if stripped else None

    @classmethod
    def from_request_args(
        cls,
        args: Dict[str, Any],
        user_id: Optional[str] = None,
        default_saved_only: bool = False,
    ) -> "QueryFilterDTO":
        """Parse, sanitize, validate, and clamp query parameters from request.args."""
        raw_keyword = _sanitize_string(args.get("keyword") or args.get("q"), max_len=MAX_KEYWORD_LENGTH)
        raw_category = _sanitize_string(args.get("category"), max_len=100)
        raw_opp_type = _sanitize_string(args.get("opportunity_type") or args.get("type"), max_len=100)
        raw_source_id = _sanitize_string(args.get("source_id") or args.get("source"), max_len=100)
        
        is_free = _parse_bool(args.get("is_free"))
        remote = _parse_bool(args.get("remote"))
        saved_only = _parse_bool(args.get("saved_only")) or default_saved_only

        raw_pricing = _sanitize_string(args.get("pricing_type") or args.get("pricing"), max_len=50)
        pricing_type = raw_pricing.lower() if raw_pricing and raw_pricing.lower() in ALLOWED_PRICING_TYPES else None

        raw_stipend = _sanitize_string(args.get("stipend_type"), max_len=50)
        stipend_type = raw_stipend.lower() if raw_stipend and raw_stipend.lower() in ALLOWED_STIPEND_TYPES else None

        raw_diff = _sanitize_string(args.get("difficulty"), max_len=50)
        difficulty = raw_diff.lower() if raw_diff and raw_diff.lower() in ALLOWED_DIFFICULTIES else None

        raw_deadline = _sanitize_string(args.get("deadline"), max_len=50)
        deadline = raw_deadline.lower() if raw_deadline in {"active", "upcoming", "past"} or (raw_deadline and re.match(r"^\d{4}-\d{2}-\d{2}$", raw_deadline)) else None

        # Sort validation against strict allowlist
        raw_sort = _sanitize_string(args.get("sort"), max_len=50)
        sort = raw_sort.lower() if raw_sort and raw_sort.lower() in ALLOWED_SORTS else ("relevance" if raw_keyword else "newest")

        raw_dir = _sanitize_string(args.get("sort_dir") or args.get("dir"), max_len=10)
        if raw_dir and raw_dir.lower() in ALLOWED_SORT_DIRS:
            sort_dir = raw_dir.lower()
        else:
            # Sane default direction depending on sort field
            sort_dir = "asc" if sort == "deadline" else "desc"

        # Pagination validation and security clamping (<= 200)
        try:
            raw_page = int(args.get("page", 1))
            page = max(1, raw_page)
        except (ValueError, TypeError):
            page = 1

        try:
            raw_per_page = int(args.get("per_page", DEFAULT_PER_PAGE))
            per_page = min(MAX_PER_PAGE, max(1, raw_per_page))
        except (ValueError, TypeError):
            per_page = DEFAULT_PER_PAGE

        raw_lifecycle = _sanitize_string(args.get("lifecycle_status") or args.get("lifecycle"), max_len=50)
        lifecycle_status = raw_lifecycle.lower() if raw_lifecycle else None

        return cls(
            keyword=raw_keyword,
            category=raw_category,
            opportunity_type=raw_opp_type,
            source_id=raw_source_id,
            is_free=is_free,
            pricing_type=pricing_type,
            stipend_type=stipend_type,
            remote=remote,
            difficulty=difficulty,
            deadline=deadline,
            sort=sort,
            sort_dir=sort_dir,
            page=page,
            per_page=per_page,
            saved_only=saved_only,
            user_id=user_id,
            lifecycle_status=lifecycle_status,
        )

    def to_query_dict(self, page: Optional[int] = None) -> Dict[str, Any]:
        """Convert active parameters into a dictionary suitable for URL generation."""
        params: Dict[str, Any] = {}
        if self.keyword:
            params["keyword"] = self.keyword
        if self.category:
            params["category"] = self.category
        if self.opportunity_type:
            params["opportunity_type"] = self.opportunity_type
        if self.source_id:
            params["source_id"] = self.source_id
        if self.is_free is not None:
            params["is_free"] = "true" if self.is_free else "false"
        if self.pricing_type:
            params["pricing_type"] = self.pricing_type
        if self.stipend_type:
            params["stipend_type"] = self.stipend_type
        if self.remote is not None:
            params["remote"] = "true" if self.remote else "false"
        if self.difficulty:
            params["difficulty"] = self.difficulty
        if self.deadline:
            params["deadline"] = self.deadline
        if self.sort and self.sort != "newest":
            params["sort"] = self.sort
        if self.sort_dir and self.sort_dir != "desc":
            params["sort_dir"] = self.sort_dir
        if self.saved_only:
            params["saved_only"] = "true"
        if self.per_page and self.per_page != DEFAULT_PER_PAGE:
            params["per_page"] = str(self.per_page)

        target_page = page if page is not None else self.page
        if target_page and target_page > 1:
            params["page"] = str(target_page)

        return params

    def to_query_string(self, page: Optional[int] = None, exclude_keys: Optional[List[str]] = None) -> str:
        """Generate a URL query string preserving active filters."""
        params = self.to_query_dict(page=page)
        if exclude_keys:
            for k in exclude_keys:
                params.pop(k, None)
        if not params:
            return ""
        return "?" + urlencode(params)

    @property
    def has_active_filters(self) -> bool:
        """Return True if any filter (excluding pagination/sorting) is active."""
        return bool(
            self.keyword
            or self.category
            or self.opportunity_type
            or self.source_id
            or self.is_free is not None
            or self.pricing_type
            or self.stipend_type
            or self.remote is not None
            or self.difficulty
            or self.deadline
            or self.saved_only
        )

    def active_filter_summary(self) -> List[Dict[str, str]]:
        """Return human-readable pills for currently active filters with reset query strings."""
        filters = []
        if self.keyword:
            filters.append({
                "key": "keyword",
                "label": f"Keyword: {self.keyword}",
                "reset_url": self.to_query_string(page=1, exclude_keys=["keyword"]),
            })
        if self.category:
            filters.append({
                "key": "category",
                "label": f"Category: {self.category.capitalize()}",
                "reset_url": self.to_query_string(page=1, exclude_keys=["category"]),
            })
        if self.opportunity_type:
            filters.append({
                "key": "opportunity_type",
                "label": f"Type: {self.opportunity_type.capitalize()}",
                "reset_url": self.to_query_string(page=1, exclude_keys=["opportunity_type"]),
            })
        if self.source_id:
            filters.append({
                "key": "source_id",
                "label": f"Source: {self.source_id}",
                "reset_url": self.to_query_string(page=1, exclude_keys=["source_id"]),
            })
        if self.is_free is not None:
            filters.append({
                "key": "is_free",
                "label": "Free Only" if self.is_free else "Paid Only",
                "reset_url": self.to_query_string(page=1, exclude_keys=["is_free"]),
            })
        if self.remote is not None:
            filters.append({
                "key": "remote",
                "label": "Remote Only" if self.remote else "On-site Only",
                "reset_url": self.to_query_string(page=1, exclude_keys=["remote"]),
            })
        if self.difficulty:
            filters.append({
                "key": "difficulty",
                "label": f"Difficulty: {self.difficulty.capitalize()}",
                "reset_url": self.to_query_string(page=1, exclude_keys=["difficulty"]),
            })
        if self.stipend_type:
            filters.append({
                "key": "stipend_type",
                "label": f"Stipend: {self.stipend_type.replace('_', ' ').capitalize()}",
                "reset_url": self.to_query_string(page=1, exclude_keys=["stipend_type"]),
            })
        if self.deadline:
            filters.append({
                "key": "deadline",
                "label": f"Deadline: {self.deadline.capitalize()}",
                "reset_url": self.to_query_string(page=1, exclude_keys=["deadline"]),
            })
        if self.saved_only:
            filters.append({
                "key": "saved_only",
                "label": "Saved Opportunities Only",
                "reset_url": self.to_query_string(page=1, exclude_keys=["saved_only"]),
            })
        return filters


@dataclass
class OpportunityCardDTO:
    """Card data transfer object for server-rendered opportunity listings."""

    id: str
    title: str
    organization: str
    category: str
    opportunity_type: str
    description_snippet: str
    url: str
    remote: bool
    location: Optional[str]
    pricing_type: Optional[str]
    is_free: bool
    stipend_type: Optional[str]
    has_stipend: bool
    difficulty: Optional[str]
    score: float
    deadline: Optional[str]
    days_until_deadline: Optional[int]
    is_expired: bool
    source_name: str
    tags: List[str] = field(default_factory=list)
    is_saved: bool = False
    relevance_rank: Optional[float] = None
    recommendation_explanation: Optional[Any] = None
    match_strength: Optional[str] = None
    eligibility_status: str = "UNKNOWN"
    lifecycle_status: str = "active"
    quality_status: str = "passed"
    is_closing_soon: bool = False
    is_verified: bool = True
    recently_updated: bool = False


@dataclass
class OpportunityDetailDTO:
    """Full detail data transfer object for server-rendered opportunity view."""

    id: str
    title: str
    organization: str
    category: str
    opportunity_type: str
    description: str
    url: str
    remote: bool
    location: Optional[str]
    pricing_type: Optional[str]
    is_free: bool
    stipend_type: Optional[str]
    stipend_amount: Optional[float]
    currency: Optional[str]
    has_stipend: bool
    difficulty: Optional[str]
    score: float
    deadline: Optional[str]
    days_until_deadline: Optional[int]
    is_expired: bool
    source_id: Optional[str]
    source_name: str
    eligibility: Optional[str]
    duration: Optional[str]
    tags: List[str] = field(default_factory=list)
    is_saved: bool = False
    created_at: str = ""
    last_harvested: str = ""
    recommendation_explanation: Optional[Any] = None
    match_strength: Optional[str] = None
    eligibility_status: str = "UNKNOWN"
    lifecycle_status: str = "active"
    quality_status: str = "passed"
    is_closing_soon: bool = False
    is_verified: bool = True
    recently_updated: bool = False
    match_analysis: Optional[Any] = None
    similar_opportunities: List[Any] = field(default_factory=list)
    recommended_for_you: List[Any] = field(default_factory=list)


@dataclass
class PaginatedResultDTO:
    """Paginated result container for SSR templates."""

    items: List[OpportunityCardDTO]
    total_count: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool
    filter_dto: QueryFilterDTO
    category_counts: Dict[str, int] = field(default_factory=dict)
    type_counts: Dict[str, int] = field(default_factory=dict)
    source_counts: Dict[str, int] = field(default_factory=dict)
