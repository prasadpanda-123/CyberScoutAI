"""
Analytics Service for CyberScout AI.

Coordinates business logic, safe parameter validation, and formatting across
Platform Market Intelligence, Private User Analytics, and Admin Telemetry.
"""

from typing import Any, Dict, List, Optional

from src.database.analytics_repository import AnalyticsRepository
from src.database.connection import DatabaseManager
from src.models.analytics_models import (
    AdminAnalyticsOverviewDTO,
    CategoryDistributionItemDTO,
    DeadlineInsightsDTO,
    EconomicInsightsDTO,
    FreshnessInsightsDTO,
    OpportunityTypeDistributionItemDTO,
    PlatformOverviewDTO,
    TrendSummaryDTO,
    UserPersonalIntelligenceDTO,
)
from src.core.logging import get_logger

logger = get_logger(__name__)

WINDOW_DAYS_MAP = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}


class AnalyticsService:
    """Domain service powering the Phase 8 analytics layer."""

    def __init__(self, repository: Optional[AnalyticsRepository] = None, db_manager: Optional[DatabaseManager] = None):
        self.repository = repository or AnalyticsRepository(db_manager=db_manager)

    def get_market_intelligence(self, window: str = "30d") -> Dict[str, Any]:
        """
        Retrieves public/authenticated market intelligence for the /analytics dashboard.
        Validates window parameter server-side.
        """
        normalized_window = window.lower().strip() if window else "30d"
        days_limit = WINDOW_DAYS_MAP.get(normalized_window, 30)

        overview = self.repository.get_platform_overview(days_limit=days_limit)
        categories = self.repository.get_category_distribution()
        types = self.repository.get_opportunity_type_distribution()
        deadlines = self.repository.get_deadline_insights()
        economics = self.repository.get_economic_insights()
        freshness = self.repository.get_freshness_insights()
        trends = self.repository.get_discovery_trends(days=days_limit or 30)

        return {
            "window": normalized_window,
            "overview": overview,
            "categories": categories,
            "opportunity_types": types,
            "deadlines": deadlines,
            "economics": economics,
            "freshness": freshness,
            "trends": trends,
        }

    def get_user_intelligence(self, user_id: Any) -> UserPersonalIntelligenceDTO:
        """
        Retrieves strictly isolated private analytics for a specific authenticated user.
        Fails closed with a safe empty DTO if user_id is invalid.
        """
        if not user_id:
            return UserPersonalIntelligenceDTO(user_id="")
        try:
            import uuid
            uid_str = str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return UserPersonalIntelligenceDTO(user_id="")
        return self.repository.get_user_personal_intelligence(user_id=uid_str)

    def get_admin_analytics(self) -> AdminAnalyticsOverviewDTO:
        """
        Retrieves operational telemetry for administrative inspection.
        """
        return self.repository.get_admin_operational_analytics()
