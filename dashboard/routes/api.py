"""
REST API Blueprint for CyberScout AI Control Center.
"""

from flask import Blueprint, jsonify, request, send_from_directory, Response, session
import json
import re
from dashboard.services.analytics_service import AnalyticsService
from dashboard.services.api_service import APIService
from dashboard.services.dashboard_service import DashboardService
from dashboard.services.statistics_service import StatisticsService
from src.auth.admin_auth import AdminSecurityManager
from src.auth.decorators import admin_required, login_required, roles_required
from src.core.constants import REPORTS_DIR
from src.core.version import get_version_info
from src.database.audit_log_repository import AuditLogRepository
from src.utils.ip_utils import get_client_ip
from src.utils.pagination_utils import parse_pagination

api_bp = Blueprint("api", __name__, url_prefix="/api")

dash_service = DashboardService()
stats_service = StatisticsService()
analytics_service = AnalyticsService()
api_service = APIService()
audit_repo = AuditLogRepository()


def get_db_manager():
    from flask import current_app
    if current_app and hasattr(current_app, "db_manager") and current_app.db_manager:
        return current_app.db_manager
    from src.database.connection import DatabaseManager
    return DatabaseManager()


@api_bp.route("/health", methods=["GET"])
def get_health():
    """GET /api/health — Full system & PostgreSQL database health status (Part 12)."""
    db_mgr = get_db_manager()
    metrics = db_mgr.get_health_metrics()
    status_code = 200 if metrics.get("connected") else 503
    return jsonify(metrics), status_code


@api_bp.route("/stats", methods=["GET"])
@api_bp.route("/dashboard/summary", methods=["GET"])
@login_required
def get_stats():
    """GET /api/dashboard/summary — KPI metrics summary."""
    summary = dash_service.get_summary_stats()
    return jsonify(summary)


@api_bp.route("/dashboard/charts", methods=["GET"])
@login_required
def get_charts():
    """GET /api/dashboard/charts — Historical timeseries and category charts dataset."""
    data = api_service.get_charts_data()
    return jsonify(data)


@api_bp.route("/opportunities", methods=["GET"])
@login_required
def get_opportunities():
    """GET /api/opportunities — Query opportunities."""
    category = request.args.get("category")
    q = request.args.get("q")
    opps = dash_service.get_opportunities(category=category, search_query=q, limit=200)
    return jsonify({"count": len(opps), "opportunities": opps})


@api_bp.route("/analytics", methods=["GET"])
@login_required
def get_analytics():
    """GET /api/analytics — Analytics charts data."""
    data = {
        "growth": analytics_service.get_growth_analytics(),
        "keywords": analytics_service.get_keyword_frequencies(),
    }
    return jsonify(data)


@api_bp.route("/providers", methods=["GET"])
@login_required
def get_providers():
    """GET /api/providers — Provider comparison stats."""
    providers = analytics_service.get_provider_comparison()
    return jsonify(providers)


@api_bp.route("/provider-health", methods=["GET"])
@login_required
def get_provider_health():
    """GET /api/provider-health — Source reliability rankings."""
    from src.intelligence.production.production_engine import ProductionEngine
    pe = ProductionEngine()
    return jsonify(pe.reliability.get_provider_rankings())


@api_bp.route("/trends", methods=["GET"])
@login_required
def get_trends():
    """GET /api/trends — Trend analytics."""
    from src.intelligence.production.production_engine import ProductionEngine
    pe = ProductionEngine()
    opps = dash_service.opp_repo.get_active_opportunities(limit=100)
    return jsonify(pe.trend_detector.analyze_trends(opps))


@api_bp.route("/freshness", methods=["GET"])
@login_required
def get_freshness():
    """GET /api/freshness — Freshness distribution stats."""
    from src.intelligence.production.production_engine import ProductionEngine
    pe = ProductionEngine()
    return jsonify(pe.metrics.to_dict())


@api_bp.route("/statistics", methods=["GET"])
@login_required
def get_statistics():
    """GET /api/statistics — General collection statistics."""
    summary = dash_service.get_summary_stats()
    return jsonify(summary)


@api_bp.route("/collectors", methods=["GET"])
@api_bp.route("/dashboard/collectors", methods=["GET"])
@admin_required
def get_collectors():
    """GET /api/dashboard/collectors — Collector status list (Sensitive)."""
    collectors = dash_service.get_collectors_status()
    resp = jsonify(collectors)
    resp.headers["Deprecation"] = "true"
    return resp


@api_bp.route("/dashboard/reports", methods=["GET"])
@api_bp.route("/reports", methods=["GET"])
@login_required
def get_reports():
    """GET /api/dashboard/reports — List of generated DOCX & CSV reports."""
    reports = api_service.get_reports_list()
    return jsonify({"count": len(reports), "reports": reports})


@api_bp.route("/system", methods=["GET"])
@admin_required
def get_system():
    """GET /api/system — System metadata (Sensitive)."""
    info = get_version_info()
    resp = jsonify(info)
    resp.headers["Deprecation"] = "true"
    return resp


@api_bp.route("/system/smtp-health", methods=["GET"])
@api_bp.route("/email/health", methods=["GET"])
@admin_required
def get_smtp_health():
    """GET /api/system/smtp-health — Returns email provider pre-flight diagnostics (Sensitive)."""
    res = api_service.check_smtp_health()
    resp = jsonify(res)
    resp.headers["Deprecation"] = "true"
    return resp


@api_bp.route("/logs", methods=["GET"])
@api_bp.route("/dashboard/logs", methods=["GET"])
@admin_required
def get_logs():
    """GET /api/dashboard/logs — Structured AppLogs (Sensitive)."""
    level = request.args.get("level")
    module = request.args.get("module")
    q = request.args.get("q")
    page, limit = parse_pagination(request, default_page=1, default_limit=50, max_limit=200)

    data = api_service.get_logs(
        level=level,
        module=module,
        search_query=q,
        page=page,
        limit=limit,
    )
    resp = jsonify(data)
    resp.headers["Deprecation"] = "true"
    return resp


@api_bp.route("/logs/export", methods=["GET"])
@admin_required
def export_logs():
    """GET /api/logs/export — Export logs in JSON format (Sensitive)."""
    data = api_service.get_logs(limit=1000)
    json_bytes = json.dumps(data.get("logs", []), indent=2, default=str).encode("utf-8")
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={
            "Content-Disposition": "attachment;filename=cyberscout_logs.json",
            "Deprecation": "true",
        },
    )


@api_bp.route("/config", methods=["GET"])
@admin_required
def get_config():
    """GET /api/config — Application settings config (Sanitized)."""
    from src.core.config import config
    resp = jsonify(config.as_sanitized_dict())
    resp.headers["Deprecation"] = "true"
    return resp


def _verify_legacy_api_csrf(admin_only: bool = True) -> bool:
    """
    Validates CSRF token for administrative state-changing operations under /api/*.
    Checks X-CSRF-Token / X-CSRFToken headers, JSON body 'csrf_token', or form 'csrf_token'.
    Requires valid matching session CSRF token. Rejects missing or invalid tokens with HTTP 403.
    """
    if admin_only:
        session_token = session.get("admin_csrf_token")
    else:
        session_token = session.get("admin_csrf_token") or session.get("user_csrf_token")

    if not session_token:
        return False

    submitted_token = None
    if request.headers.get("X-CSRF-Token"):
        submitted_token = request.headers.get("X-CSRF-Token").strip()
    elif request.headers.get("X-CSRFToken"):
        submitted_token = request.headers.get("X-CSRFToken").strip()
    elif request.is_json and request.json and isinstance(request.json, dict) and "csrf_token" in request.json:
        submitted_token = str(request.json.get("csrf_token", "")).strip()
    elif request.form and "csrf_token" in request.form:
        submitted_token = str(request.form.get("csrf_token", "")).strip()

    if not submitted_token:
        return False

    return AdminSecurityManager.verify_csrf_token(session_token, submitted_token)


# POST Action Commands with JSON error safety and Admin authentication
@api_bp.route("/run", methods=["POST"])
@admin_required
def trigger_run():
    """POST /api/run — Trigger asynchronous background scan job (Sensitive)."""
    if not _verify_legacy_api_csrf():
        return jsonify({"success": False, "status": "failed", "error": "CSRF token validation failed"}), 403
    from src.automation.job_manager import ScanInProgressError
    db_mgr = get_db_manager()
    if not db_mgr.ping():
        from src.core.logging import get_logger
        get_logger(__name__).error("Scan aborted: Database unavailable")
        return jsonify({"success": False, "error": "Database unavailable", "status": "failed"}), 503
    try:
        dry_run = False
        if request.is_json and request.json:
            dry_run = bool(request.json.get("dry_run", False))
        res = api_service.trigger_scan(dry_run=dry_run)
        try:
            audit_repo.log_event("COLLECTORS", "TRIGGER_RUN", "SUCCESS", source_ip=get_client_ip(request), details=f"Scan job launched via /api/run (job_id={res.get('job_id')})")
        except Exception:
            pass
        resp = jsonify({
            "status": "accepted",
            "success": True,
            "job_id": res.get("job_id"),
            "message": "Scan started successfully",
        })
        resp.headers["Deprecation"] = "true"
        return resp, 202
    except ScanInProgressError as err:
        return jsonify({"success": False, "error": str(err), "status": "running"}), 409
    except Exception as e:
        try:
            audit_repo.log_event("COLLECTORS", "TRIGGER_RUN", "FAILED", source_ip=get_client_ip(request), details=str(e))
        except Exception:
            pass
        return jsonify({"success": False, "status": "failed", "error": str(e)}), 400


@api_bp.route("/jobs/<job_id>", methods=["GET"])
@api_bp.route("/scan/status/<job_id>", methods=["GET"])
@admin_required
def get_job_status(job_id: str):
    """GET /api/jobs/<job_id> & GET /api/scan/status/<job_id> — Return scan job status telemetry."""
    if not re.match(r"^[0-9a-fA-F-]{8,64}$", job_id):
        return jsonify({"error": "Invalid job identifier format", "job_id": job_id}), 400
    job = api_service.get_job_status(job_id)
    if not job:
        return jsonify({"error": "Job not found", "job_id": job_id}), 404
    resp = jsonify(job)
    resp.headers["Deprecation"] = "true"
    return resp


@api_bp.route("/email/test", methods=["POST"])
@admin_required
def email_test():
    """POST /api/email/test — Dispatch test HTML email (Sensitive)."""
    if not _verify_legacy_api_csrf(admin_only=True):
        return jsonify({"status": "failed", "error": "CSRF token validation failed"}), 403
    try:
        res = api_service.send_test_email()
        status_code = 200 if res.get("success", True) else 400
        audit_repo.log_event("EMAIL", "TEST_EMAIL", "SUCCESS" if res.get("success", True) else "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Test email dispatched via /api/email/test")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp, status_code
    except Exception as e:
        audit_repo.log_event("EMAIL", "TEST_EMAIL", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Error sending test email: {e}")
        return jsonify({"status": "failed", "error": str(e)}), 400


@api_bp.route("/scheduler/pause", methods=["POST"])
@admin_required
def scheduler_pause():
    """POST /api/scheduler/pause — Pause scheduler (Sensitive)."""
    if not _verify_legacy_api_csrf(admin_only=True):
        return jsonify({"status": "failed", "error": "CSRF token validation failed"}), 403
    try:
        res = api_service.pause_scheduler()
        audit_repo.log_event("SCHEDULER", "PAUSE_SCHEDULER", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Scheduler paused via /api/scheduler/pause")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        audit_repo.log_event("SCHEDULER", "PAUSE_SCHEDULER", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Failed to pause scheduler: {e}")
        return jsonify({"status": "failed", "error": str(e)})


@api_bp.route("/scheduler/resume", methods=["POST"])
@admin_required
def scheduler_resume():
    """POST /api/scheduler/resume — Resume scheduler (Sensitive)."""
    if not _verify_legacy_api_csrf(admin_only=True):
        return jsonify({"status": "failed", "error": "CSRF token validation failed"}), 403
    try:
        res = api_service.resume_scheduler()
        audit_repo.log_event("SCHEDULER", "RESUME_SCHEDULER", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Scheduler resumed via /api/scheduler/resume")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        audit_repo.log_event("SCHEDULER", "RESUME_SCHEDULER", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Failed to resume scheduler: {e}")
        return jsonify({"status": "failed", "error": str(e)})


@api_bp.route("/scheduler/restart", methods=["POST"])
@admin_required
def scheduler_restart():
    """POST /api/scheduler/restart — Restart scheduler (Sensitive)."""
    if not _verify_legacy_api_csrf(admin_only=True):
        return jsonify({"success": False, "status": "failed", "error": "CSRF token validation failed"}), 403
    try:
        res = api_service.restart_scheduler()
        audit_repo.log_event("SCHEDULER", "RESTART_SCHEDULER", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Scheduler restarted via /api/scheduler/restart")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        audit_repo.log_event("SCHEDULER", "RESTART_SCHEDULER", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Failed to restart scheduler: {e}")
        return jsonify({"success": False, "status": "failed", "error": str(e)})


@api_bp.route("/report/trigger", methods=["POST"])
@admin_required
def trigger_daily_report():
    """POST /api/report/trigger — Send Daily Report Now (Sensitive)."""
    if not _verify_legacy_api_csrf(admin_only=True):
        return jsonify({"success": False, "status": "failed", "error": "CSRF token validation failed"}), 403
    try:
        res = api_service.send_daily_report_now()
        audit_repo.log_event("REPORTS", "TRIGGER_REPORT", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Daily report triggered via /api/report/trigger")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        audit_repo.log_event("REPORTS", "TRIGGER_REPORT", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Failed to trigger daily report: {e}")
        return jsonify({"success": False, "status": "failed", "error": str(e)})


@api_bp.route("/opportunities/clear-old", methods=["POST"])
@admin_required
def clear_old_opportunities():
    """POST /api/opportunities/clear-old — Clear Old Opportunities (Sensitive)."""
    if not _verify_legacy_api_csrf(admin_only=True):
        return jsonify({"success": False, "status": "failed", "error": "CSRF token validation failed"}), 403
    try:
        days = 30
        if request.is_json and request.json:
            try:
                raw_days = request.json.get("days", 30)
                days = int(raw_days)
                if days < 1:
                    days = 30
            except (ValueError, TypeError):
                days = 30
        res = api_service.clear_old_opportunities(days=days)
        audit_repo.log_event("OPPORTUNITIES", "CLEAR_OLD", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Old opportunities cleared ({days} days) via /api/opportunities/clear-old")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        audit_repo.log_event("OPPORTUNITIES", "CLEAR_OLD", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Failed to clear old opportunities: {e}")
        return jsonify({"success": False, "status": "failed", "error": str(e)})


@api_bp.route("/analytics/refresh", methods=["POST"])
@admin_required
def refresh_analytics():
    """POST /api/analytics/refresh — Refresh Analytics (Sensitive)."""
    if not _verify_legacy_api_csrf(admin_only=True):
        return jsonify({"success": False, "status": "failed", "error": "CSRF token validation failed"}), 403
    try:
        res = api_service.refresh_analytics()
        audit_repo.log_event("ANALYTICS", "REFRESH", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Analytics refreshed via /api/analytics/refresh")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        audit_repo.log_event("ANALYTICS", "REFRESH", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Failed to refresh analytics: {e}")
        return jsonify({"success": False, "status": "failed", "error": str(e)})

