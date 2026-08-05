"""
Analytics & Quality Intelligence Page Route (Page 3).
"""

from flask import Blueprint, render_template
from dashboard.services.analytics_service import AnalyticsService
from src.auth.decorators import login_required

analytics_bp = Blueprint("analytics_ui", __name__)
analytics_service = AnalyticsService()


@analytics_bp.route("/analytics")
@login_required
def index():
    """Renders Analytics & Quality Intelligence dashboard page."""
    growth = analytics_service.get_growth_analytics()
    providers = analytics_service.get_provider_comparison()
    keywords = analytics_service.get_keyword_frequencies()

    return render_template(
        "analytics.html",
        active_page="analytics",
        growth=growth,
        providers=providers,
        keywords=keywords,
    )
