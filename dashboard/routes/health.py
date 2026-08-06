"""
System Health Status & Telemetry API Route (Part 12).
"""

from flask import Blueprint, jsonify, render_template, request
from dashboard.services.dashboard_service import DashboardService
from src.database.connection import DatabaseManager

health_bp = Blueprint("health", __name__)
dash_service = DashboardService()
db_manager = DatabaseManager()


@health_bp.route("/api/health", methods=["GET"])
def api_health():
    """
    Returns structured JSON system and database health status (Part 12).
    """
    metrics = db_manager.get_health_metrics()
    metrics["healthy"] = metrics.get("status") == "ok"
    status_code = 200 if metrics["status"] == "ok" else 503
    return jsonify(metrics), status_code


@health_bp.route("/health")
def index():
    """Renders visual system health dashboard or returns JSON health metrics."""
    if (
        request.headers.get("Accept") == "application/json"
        or request.args.get("format") == "json"
        or "json" in request.headers.get("Accept", "").lower()
    ):
        return api_health()

    report = dash_service.get_health_report()
    metrics = db_manager.get_health_metrics()
    return render_template(
        "health.html",
        active_page="health",
        health_report=report,
        db_metrics=metrics,
    )

