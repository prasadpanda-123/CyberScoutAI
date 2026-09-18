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


@health_bp.route("/health/live", methods=["GET"])
@health_bp.route("/api/health/live", methods=["GET"])
def health_liveness():
    """
    Liveness probe: verifies the application worker process is alive and responsive.
    Does NOT require database or external services to be reachable.
    """
    return jsonify({
        "status": "ok",
        "service": "CyberScout AI",
        "alive": True,
    }), 200


@health_bp.route("/health/ready", methods=["GET"])
@health_bp.route("/api/health/ready", methods=["GET"])
def health_readiness():
    """
    Readiness probe: verifies the application can actively serve user requests.
    Checks PostgreSQL connectivity without exposing credentials, secrets, or internal paths.
    """
    db_mgr = get_db_manager()
    is_ready = False
    try:
        is_ready = bool(db_mgr.ping())
    except Exception:
        is_ready = False

    if is_ready:
        return jsonify({
            "status": "ok",
            "service": "CyberScout AI",
            "ready": True,
            "database": "connected",
        }), 200
    else:
        return jsonify({
            "status": "degraded",
            "service": "CyberScout AI",
            "ready": False,
            "database": "unavailable",
        }), 503


@health_bp.route("/health")
def index():
    """Renders visual system health dashboard or returns JSON health metrics."""
    if (
        request.headers.get("Accept") == "application/json"
        or request.args.get("format") == "json"
        or "json" in request.headers.get("Accept", "").lower()
    ):
        return api_health()

    db_mgr = get_db_manager()
    report = dash_service.get_health_report()
    metrics = db_mgr.get_health_metrics()
    return render_template(
        "health.html",
        active_page="health",
        health_report=report,
        db_metrics=metrics,
    )

