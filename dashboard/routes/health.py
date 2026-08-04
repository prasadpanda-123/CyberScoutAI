"""
System Health Status Route (Page 10).
"""

from flask import Blueprint, render_template
from dashboard.services.dashboard_service import DashboardService

health_bp = Blueprint("health_ui", __name__)
dash_service = DashboardService()


@health_bp.route("/health")
def index():
    """Renders visual system health dashboard."""
    report = dash_service.get_health_report()
    return render_template(
        "health.html",
        active_page="health",
        health_report=report,
    )
