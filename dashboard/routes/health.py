"""
System Health Status & Telemetry API Route (Part 12).
"""

from flask import Blueprint, current_app, jsonify, render_template, request
from dashboard.services.dashboard_service import DashboardService
from src.database.connection import DatabaseManager

health_bp = Blueprint("health", __name__)
dash_service = DashboardService()


def get_db_manager():
    if current_app and hasattr(current_app, "db_manager") and current_app.db_manager:
        return current_app.db_manager
    return DatabaseManager()


@health_bp.route("/api/health", methods=["GET"])
def api_health():
    """
    Returns structured JSON system and database health status.
    """
    db_mgr = get_db_manager()
    metrics = db_mgr.get_health_metrics()
    metrics["healthy"] = metrics.get("connected", False)
    status_code = 200 if metrics.get("connected") else 503
    return jsonify(metrics), status_code


@health_bp.route("/api/health/database", methods=["GET"])
def api_health_database():
    """
    Returns exact Part 7 database health JSON payload.
    """
    db_mgr = get_db_manager()
    metrics = db_mgr.get_health_metrics()
    status_code = 200 if metrics.get("connected") else 503
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

