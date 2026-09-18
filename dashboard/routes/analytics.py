"""
Analytics & Platform Market Intelligence Page Route.
"""

from flask import Blueprint, render_template, request
from dashboard.services.analytics_service import AnalyticsService
from src.auth.decorators import login_required

analytics_bp = Blueprint("analytics_ui", __name__)
analytics_service = AnalyticsService()


@analytics_bp.route("/analytics")
@login_required
def index():
    """Renders Platform & Market Intelligence analytics dashboard."""
    window = request.args.get("window", "30d")
    intel = analytics_service.get_market_intelligence(window=window)

    return render_template(
        "analytics.html",
        active_page="analytics",
        intel=intel,
        window=intel["window"],
        overview=intel["overview"],
        categories=intel["categories"],
        opportunity_types=intel["opportunity_types"],
        deadlines=intel["deadlines"],
        economics=intel["economics"],
        freshness=intel["freshness"],
        trends=intel["trends"],
    )
