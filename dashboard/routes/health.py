"""
System Health Status Route (Page 10).
"""

from flask import Blueprint, jsonify, render_template, request
from dashboard.services.dashboard_service import DashboardService

health_bp = Blueprint("health_ui", __name__)
dash_service = DashboardService()


@health_bp.route("/health")
def index():
    """Renders visual system health dashboard or returns JSON for health probes."""
    if (
        request.headers.get("Accept") == "application/json"
        or request.args.get("format") == "json"
        or "json" in request.headers.get("Accept", "").lower()
    ):
        return jsonify({"healthy": True}), 200

    report = dash_service.get_health_report()
    return render_template(
        "health.html",
        active_page="health",
        health_report=report,
    )
