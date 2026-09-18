"""
Analytics Service adapter for CyberScout AI dashboard presentation layer.
Delegates to the authoritative src.services.analytics_service.AnalyticsService.
"""

from typing import Any, Dict, List, Optional
from src.database.connection import DatabaseManager
from src.services.analytics_service import AnalyticsService as DomainAnalyticsService


class AnalyticsService:
    """Provides historical growth, provider performance, and keyword analytics."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.domain_service = DomainAnalyticsService(db_manager=self.db_manager)

    def get_market_intelligence(self, window: str = "30d") -> Dict[str, Any]:
        """Returns market and platform intelligence."""
        return self.domain_service.get_market_intelligence(window=window)

    def get_user_intelligence(self, user_id: Any) -> Any:
        """Returns private user intelligence."""
        return self.domain_service.get_user_intelligence(user_id=user_id)

    def get_admin_analytics(self) -> Any:
        """Returns administrative operational analytics."""
        return self.domain_service.get_admin_analytics()

    def get_growth_analytics(self) -> Dict[str, Any]:
        """Returns growth metrics derived from database trends."""
        trends = self.domain_service.repository.get_discovery_trends(days=30)
        return {
            "daily_growth_pct": trends.percentage_change if trends.percentage_change is not None else 0.0,
            "weekly_growth_pct": trends.percentage_change if trends.percentage_change is not None else 0.0,
            "monthly_growth_pct": trends.percentage_change if trends.percentage_change is not None else 0.0,
            "growth_labels": [p.period_label for p in trends.points[-7:]],
            "growth_values": [p.count for p in trends.points[-7:]],
        }

    def get_provider_comparison(self) -> List[Dict[str, Any]]:
        """Returns provider reliability and yield comparison stats."""
        sources = self.domain_service.repository.get_admin_operational_analytics().source_health_summary
        return [
            {
                "provider": s.source_id,
                "yield_count": s.items_seen,
                "avg_quality_score": round(100.0 - s.malformed_rate, 1),
            }
            for s in sources[:5]
        ]

    def get_keyword_frequencies(self) -> Dict[str, int]:
        """Returns top keyword extraction frequencies from categories."""
        cats = self.domain_service.repository.get_category_distribution(limit=6)
        return {c.category: c.count for c in cats}
