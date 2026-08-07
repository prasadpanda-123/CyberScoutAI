"""
Protected Administrative REST API Blueprint (Phase 4 & Phase 5).

Provides JSON APIs for administrative actions, logs, system config, scheduler, and collectors.
Requires admin session authentication via `@admin_required`.
"""

import json
from flask import Blueprint, jsonify, request, Response
from dashboard.services.analytics_service import AnalyticsService
from dashboard.services.api_service import APIService
from dashboard.services.dashboard_service import DashboardService
from src.auth.decorators import admin_required
from src.core.version import get_version_info
from src.database.audit_log_repository import AuditLogRepository
from src.database.log_repository import LogRepository

admin_api_bp = Blueprint("admin_api", __name__, url_prefix="/admin/api")

dash_service = DashboardService()
analytics_service = AnalyticsService()
api_service = APIService()
audit_repo = AuditLogRepository()
log_repo = LogRepository()


@admin_api_bp.route("/system", methods=["GET"])
@admin_api_bp.route("/system/info", methods=["GET"])
@admin_required
def admin_get_system():
    """GET /admin/api/system — System metadata."""
    info = get_version_info()
    return jsonify(info)


@admin_api_bp.route("/system/smtp-health", methods=["GET"])
@admin_api_bp.route("/email/health", methods=["GET"])
@admin_required
def admin_get_smtp_health():
    """GET /admin/api/system/smtp-health — SMTP health check."""
    res = api_service.check_smtp_health()
    return jsonify(res)


@admin_api_bp.route("/logs", methods=["GET"])
@admin_required
def admin_get_logs():
    """GET /admin/api/logs — Query structured app logs."""
    level = request.args.get("level")
    module = request.args.get("module")
    q = request.args.get("q")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))

    data = api_service.get_logs(
        level=level,
        module=module,
        search_query=q,
        page=page,
        limit=limit,
    )
    return jsonify(data)


@admin_api_bp.route("/audit-logs", methods=["GET"])
@admin_required
def admin_get_audit_logs():
    """GET /admin/api/audit-logs — Query security audit trail logs."""
    q = request.args.get("q")
    event_type = request.args.get("event_type")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))

    data = audit_repo.query_logs(
        event_type=event_type,
        search_query=q,
        page=page,
        limit=limit,
    )
    return jsonify(data)


@admin_api_bp.route("/logs/export", methods=["GET"])
@admin_required
def admin_export_logs():
    """GET /admin/api/logs/export — Export logs in JSON format."""
    data = api_service.get_logs(limit=1000)
    json_bytes = json.dumps(data.get("logs", []), indent=2).encode("utf-8")
    audit_repo.log_event("LOGS", "EXPORT_LOGS", "SUCCESS", source_ip=request.remote_addr, details="Exported app logs JSON")
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=cyberscout_admin_logs.json"},
    )


@admin_api_bp.route("/config", methods=["GET"])
@admin_required
def admin_get_config():
    """GET /admin/api/config — Application settings configuration."""
    from src.core.config import config
    return jsonify(config.as_dict())


@admin_api_bp.route("/collectors", methods=["GET"])
@admin_required
def admin_get_collectors():
    """GET /admin/api/collectors — Collector status list."""
    collectors = dash_service.get_collectors_status()
    return jsonify(collectors)


def get_db_manager():
    from flask import current_app
    if current_app and hasattr(current_app, "db_manager") and current_app.db_manager:
        return current_app.db_manager
    from src.database.connection import DatabaseManager
    return DatabaseManager()


@admin_api_bp.route("/run", methods=["POST"])
@admin_required
def admin_trigger_run():
    """POST /admin/api/run — Trigger background scan job."""
    from src.automation.job_manager import ScanInProgressError
    db_mgr = get_db_manager()
    if not db_mgr.ping():
        from src.core.logging import get_logger
        get_logger(__name__).error("Scan aborted: Database unavailable")
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        dry_run = False
        if request.is_json and request.json:
            dry_run = bool(request.json.get("dry_run", False))
        res = api_service.trigger_scan(dry_run=dry_run)
        audit_repo.log_event("COLLECTORS", "TRIGGER_RUN", "SUCCESS", source_ip=request.remote_addr, details=f"Scan job launched (job_id={res.get('job_id')})")
        return jsonify(res), 200
    except ScanInProgressError as err:
        return jsonify({"success": False, "error": str(err), "status": "running"}), 409
    except Exception as e:
        audit_repo.log_event("COLLECTORS", "TRIGGER_RUN", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"success": False, "status": "failed", "error": str(e)}), 500


@admin_api_bp.route("/jobs/<job_id>", methods=["GET"])
@admin_required
def admin_get_job_status(job_id: str):
    """GET /admin/api/jobs/<job_id> — Return scan job status telemetry."""
    job = api_service.get_job_status(job_id)
    if not job:
        return jsonify({"error": "Job not found", "job_id": job_id}), 404
    return jsonify(job)


@admin_api_bp.route("/email/test", methods=["POST"])
@admin_required
def admin_email_test():
    """POST /admin/api/email/test — Dispatch test HTML email."""
    try:
        res = api_service.send_test_email()
        audit_repo.log_event("EMAIL", "TEST_EMAIL", "SUCCESS", source_ip=request.remote_addr, details="Test email dispatched")
        return jsonify(res)
    except Exception as e:
        audit_repo.log_event("EMAIL", "TEST_EMAIL", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/scheduler/pause", methods=["POST"])
@admin_required
def admin_scheduler_pause():
    """POST /admin/api/scheduler/pause — Pause task scheduler."""
    try:
        res = api_service.pause_scheduler()
        audit_repo.log_event("SCHEDULER", "PAUSE_SCHEDULER", "SUCCESS", source_ip=request.remote_addr, details="Scheduler paused")
        return jsonify(res)
    except Exception as e:
        audit_repo.log_event("SCHEDULER", "PAUSE_SCHEDULER", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/scheduler/resume", methods=["POST"])
@admin_required
def admin_scheduler_resume():
    """POST /admin/api/scheduler/resume — Resume task scheduler."""
    try:
        res = api_service.resume_scheduler()
        audit_repo.log_event("SCHEDULER", "RESUME_SCHEDULER", "SUCCESS", source_ip=request.remote_addr, details="Scheduler resumed")
        return jsonify(res)
    except Exception as e:
        audit_repo.log_event("SCHEDULER", "RESUME_SCHEDULER", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/scheduler/restart", methods=["POST"])
@admin_required
def admin_scheduler_restart():
    """POST /admin/api/scheduler/restart — Restart task scheduler."""
    try:
        api_service.pause_scheduler()
        res = api_service.resume_scheduler()
        audit_repo.log_event("SCHEDULER", "RESTART_SCHEDULER", "SUCCESS", source_ip=request.remote_addr, details="Scheduler restarted")
        return jsonify({"status": "restarted", "message": "Scheduler service restarted successfully."})
    except Exception as e:
        audit_repo.log_event("SCHEDULER", "RESTART_SCHEDULER", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/db/test", methods=["POST", "GET"])
@admin_required
def admin_db_test():
    """POST /admin/api/db/test — Test database connection."""
    from src.database.connection import DatabaseManager
    db = DatabaseManager()
    is_ok = db.ping()
    audit_repo.log_event("DATABASE", "TEST_CONNECTION", "SUCCESS" if is_ok else "FAILED", source_ip=request.remote_addr, details=f"Database test status: {'Connected' if is_ok else 'Disconnected'}")
    return jsonify({
        "status": "success" if is_ok else "failed",
        "connected": is_ok,
        "database_type": "PostgreSQL",
        "message": "Database connection verified." if is_ok else "Database connection ping failed.",
    })


@admin_api_bp.route("/db/health", methods=["GET"])
@admin_required
def admin_db_health():
    """GET /admin/api/db/health — Show database health & telemetry metrics."""
    from src.database.connection import DatabaseManager
    db = DatabaseManager()
    metrics = db.get_health_metrics()
    return jsonify(metrics)


@admin_api_bp.route("/db/reconnect", methods=["POST"])
@admin_required
def admin_db_reconnect():
    """POST /admin/api/db/reconnect — Force database connection reset and reconnect."""
    from src.database.connection import DatabaseManager
    from src.database.engine import reset_engine
    try:
        reset_engine()
        db = DatabaseManager()
        db.close_connection()
        is_ok = db.check_connection_with_backoff(max_retries=3)
        audit_repo.log_event("DATABASE", "RECONNECT_DB", "SUCCESS" if is_ok else "FAILED", source_ip=request.remote_addr, details="Reconnected database engine pool")
        return jsonify({
            "status": "success" if is_ok else "failed",
            "connected": is_ok,
            "message": "PostgreSQL engine pool reconnected successfully." if is_ok else "Failed to reconnect to PostgreSQL database.",
        })
    except Exception as e:
        audit_repo.log_event("DATABASE", "RECONNECT_DB", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/report/trigger", methods=["POST"])
@admin_required
def admin_trigger_report():
    """POST /admin/api/report/trigger — Dispatch daily digest report immediately."""
    try:
        res = api_service.send_daily_report_now()
        audit_repo.log_event("REPORTS", "TRIGGER_REPORT", "SUCCESS", source_ip=request.remote_addr, details="Daily report digest triggered")
        return jsonify(res)
    except Exception as e:
        audit_repo.log_event("REPORTS", "TRIGGER_REPORT", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/analytics/refresh", methods=["POST"])
@admin_required
def admin_refresh_analytics():
    """POST /admin/api/analytics/refresh — Recalculate provider statistics."""
    try:
        res = api_service.refresh_analytics()
        audit_repo.log_event("ANALYTICS", "REFRESH_STATS", "SUCCESS", source_ip=request.remote_addr, details="Analytics metrics refreshed")
        return jsonify(res)
    except Exception as e:
        audit_repo.log_event("ANALYTICS", "REFRESH_STATS", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/opportunities/clear-old", methods=["POST"])
@admin_required
def admin_clear_old_opportunities():
    """POST /admin/api/opportunities/clear-old — Purge records older than 30 days."""
    try:
        res = api_service.clear_old_opportunities(days=30)
        audit_repo.log_event("OPPORTUNITIES", "CLEAR_OLD", "SUCCESS", source_ip=request.remote_addr, details=f"Purged {res.get('deleted_count', 0)} old records")
        return jsonify(res)
    except Exception as e:
        audit_repo.log_event("OPPORTUNITIES", "CLEAR_OLD", "FAILED", source_ip=request.remote_addr, details=str(e))
        return jsonify({"status": "failed", "error": str(e)})


@admin_api_bp.route("/db/info", methods=["GET"])
@admin_required
def admin_db_info():
    """GET /admin/api/db/info — Show PostgreSQL host (masked), version, and table counts."""
    from src.database.connection import DatabaseManager
    db = DatabaseManager()
    metrics = db.get_health_metrics()
    return jsonify(metrics)

