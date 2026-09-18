"""
Analytics & Intelligence Data Transfer Objects (DTOs) for CyberScout AI.

Defines deterministic, strongly typed models for platform metrics, category
distributions, opportunity types, deadline radar, economic models, discovery trends,
private user insights, and administrator operational analytics.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class PlatformOverviewDTO:
    """High-level platform-wide opportunity volume and lifecycle breakdown."""

    total_opportunities: int = 0
    active_opportunities: int = 0
    closing_soon_opportunities: int = 0
    new_this_week_opportunities: int = 0
    new_this_month_opportunities: int = 0
    reopened_opportunities: int = 0
    expired_opportunities: int = 0
    removed_opportunities: int = 0
    quarantined_opportunities: int = 0

    # Economic Breakdown
    free_opportunities: int = 0
    paid_opportunities: int = 0
    freemium_opportunities: int = 0
    unknown_pricing_opportunities: int = 0

    # Attributes
    remote_opportunities: int = 0
    stipend_opportunities: int = 0
    certificate_opportunities: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CategoryDistributionItemDTO:
    """Distribution metric for a single opportunity category."""

    category: str
    count: int
    percentage: float
    active_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OpportunityTypeDistributionItemDTO:
    """Distribution metric for a single opportunity type."""

    opportunity_type: str
    count: int
    percentage: float
    active_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeadlineInsightsDTO:
    """Bucket-based urgency metrics for active opportunities with deadlines."""

    due_today: int = 0
    due_within_24h: int = 0
    due_within_3d: int = 0
    due_within_7d: int = 0
    due_within_30d: int = 0
    total_with_deadlines: int = 0
    total_without_deadlines: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EconomicInsightsDTO:
    """Aggregated financial and pricing analytics."""

    free_count: int = 0
    paid_count: int = 0
    freemium_count: int = 0
    unknown_count: int = 0
    stipend_available_count: int = 0
    certificate_available_count: int = 0
    with_application_fee_count: int = 0
    average_stipend: Optional[float] = None
    stipend_currency_breakdown: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FreshnessInsightsDTO:
    """Platform freshness health metrics (Phase 6 semantics)."""

    fresh_count: int = 0
    aging_count: int = 0
    stale_count: int = 0
    severely_stale_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendPointDTO:
    """A single time-series bucket point for discovery velocity."""

    period_label: str
    date_start: str
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendSummaryDTO:
    """Deterministic comparison between current period and previous period."""

    metric_name: str
    current_period_count: int
    previous_period_count: int
    absolute_change: int
    percentage_change: Optional[float]  # None if previous was 0 and current was 0, or float
    trend_direction: str  # "up", "down", "flat"
    points: List[TrendPointDTO] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserPersonalIntelligenceDTO:
    """Private personal insights for an individual authenticated user."""

    user_id: Any = ""
    total_saved: int = 0
    active_saved: int = 0
    closing_soon_saved: int = 0
    expired_saved: int = 0
    top_saved_categories: List[Dict[str, Any]] = field(default_factory=list)
    top_saved_types: List[Dict[str, Any]] = field(default_factory=list)

    # Preferences & Profile
    preferred_categories: List[str] = field(default_factory=list)
    preferred_types: List[str] = field(default_factory=list)
    prefers_remote: Optional[bool] = None
    preferred_location: Optional[str] = None
    skills: List[str] = field(default_factory=list)

    # Search & Notification Activity
    recent_searches: List[Dict[str, Any]] = field(default_factory=list)
    frequent_search_terms: List[Dict[str, Any]] = field(default_factory=list)
    notifications_received: int = 0
    unread_notifications: int = 0
    notification_breakdown: Dict[str, int] = field(default_factory=dict)
    saved_deadlines_within_7d: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceAnalyticsDTO:
    """Source-level operational metrics and health status."""

    source_id: str
    health_status: str
    items_seen: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_rejected: int = 0
    failure_count: int = 0
    success_count: int = 0
    malformed_rate: float = 0.0
    latency: float = 0.0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdminAnalyticsOverviewDTO:
    """Aggregated operational intelligence for administrative inspection."""

    platform_overview: PlatformOverviewDTO
    source_health_summary: List[SourceAnalyticsDTO]
    lifecycle_distribution: Dict[str, int]
    quality_distribution: Dict[str, int]
    quarantine_summary: Dict[str, Any]
    notification_metrics: Dict[str, Any]
    recent_trends: TrendSummaryDTO

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
