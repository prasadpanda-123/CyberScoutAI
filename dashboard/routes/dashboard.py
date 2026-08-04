"""
Dashboard Overview Page Route (Page 1).
"""

from flask import Blueprint, jsonify, render_template, request
from dashboard.services.dashboard_service import DashboardService
from dashboard.services.statistics_service import StatisticsService
from src.core.version import get_version_info

dashboard_bp = Blueprint("dashboard_ui", __name__)
dash_service = DashboardService()
stats_service = StatisticsService()


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
def index():
    """Renders main Overview Dashboard page or returns JSON status info."""
    if (
        request.headers.get("Accept") == "application/json"
        or request.args.get("format") == "json"
    ):
        info = get_version_info()
        return jsonify({
            "status": "ok",
            "application": info.get("app_name", "CyberScout AI"),
            "version": info.get("version", "1.2.0"),
        }), 200

    summary = dash_service.get_summary_stats()
    cat_dist = stats_service.get_category_distribution()
    prio_dist = stats_service.get_priority_distribution()
    src_dist = stats_service.get_source_distribution()
    daily_trends = stats_service.get_daily_opportunity_trends()

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        summary=summary,
        category_distribution=cat_dist,
        priority_distribution=prio_dist,
        source_distribution=src_dist,
        daily_trends=daily_trends,
    )
