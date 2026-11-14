"""
REST API Blueprint for CyberScout AI Control Center.
"""

from flask import Blueprint, jsonify, request, send_from_directory, Response, session
import dataclasses
import json
import re
from dashboard.services.analytics_service import AnalyticsService
from dashboard.services.api_service import APIService
from dashboard.services.dashboard_service import DashboardService
from dashboard.services.statistics_service import StatisticsService
from src.auth.decorators import admin_required, login_required, roles_required
from src.core.constants import REPORTS_DIR
from src.core.logging import get_logger
from src.core.version import get_version_info
from src.database.audit_log_repository import AuditLogRepository
from src.database.notification_repository import NotificationRepository
from src.database.opportunity_repository import OpportunityRepository
from src.models.query_filter_dto import QueryFilterDTO
from src.services.opportunity_service import OpportunityService
from src.utils.ip_utils import get_client_ip
from src.utils.pagination_utils import parse_pagination

logger = get_logger(__name__)

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
    """GET /api/opportunities — Return validated, user-aware paginated opportunity cards."""
    user_id = session.get("user_id") or session.get("admin_user_id")
    try:
        filters = QueryFilterDTO.from_request_args(
            request.args,
            user_id=str(user_id) if user_id else None,
        )
        result = OpportunityService().search_opportunities(filters)
        opportunities = [dataclasses.asdict(item) for item in result.items]
        return jsonify({
            "status": "success",
            "count": len(opportunities),
            "total": result.total_count,
            "opportunities": opportunities,
            "page": result.page,
            "per_page": result.per_page,
            "total_pages": result.total_pages,
            "has_next": result.has_next,
            "has_prev": result.has_prev,
        })
    except Exception as e:
        logger.error(f"Failed to fetch opportunities: {e}", exc_info=True)
        return jsonify({
            "status": "failed",
            "error": "Failed to fetch opportunities from database. Please try again.",
            "opportunities": [],
            "count": 0,
            "total": 0,
            "page": 1,
            "per_page": 9,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False,
        }), 500


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
@admin_required
def get_reports():
    """GET /api/dashboard/reports — List of generated DOCX & CSV reports (Sensitive)."""
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



# POST Action Commands with JSON error safety and Admin authentication
@api_bp.route("/run", methods=["POST"])
@admin_required
def trigger_run():
    """POST /api/run — Trigger asynchronous background scan job (Sensitive)."""
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
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Scan trigger execution failure: {e}", exc_info=True)
        try:
            audit_repo.log_event("COLLECTORS", "TRIGGER_RUN", "FAILED", source_ip=get_client_ip(request), details=f"Scan error: {type(e).__name__}")
        except Exception:
            pass
        return jsonify({"success": False, "status": "failed", "error": "Failed to trigger scan execution. Please inspect system logs."}), 500


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
    try:
        res = api_service.send_test_email()
        status_code = 200 if res.get("success", True) else 400
        audit_repo.log_event("EMAIL", "TEST_EMAIL", "SUCCESS" if res.get("success", True) else "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Test email dispatched via /api/email/test")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp, status_code
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Error sending test email: {e}", exc_info=True)
        audit_repo.log_event("EMAIL", "TEST_EMAIL", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Failed to send test email")
        return jsonify({"status": "failed", "error": "Failed to send test email. Please verify SMTP configuration."}), 500


@api_bp.route("/scheduler/pause", methods=["POST"])
@admin_required
def scheduler_pause():
    """POST /api/scheduler/pause — Pause scheduler (Sensitive)."""
    try:
        res = api_service.pause_scheduler()
        audit_repo.log_event("SCHEDULER", "PAUSE_SCHEDULER", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Scheduler paused via /api/scheduler/pause")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to pause scheduler: {e}", exc_info=True)
        audit_repo.log_event("SCHEDULER", "PAUSE_SCHEDULER", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Failed to pause scheduler")
        return jsonify({"status": "failed", "error": "Failed to pause scheduler. Check server logs."}), 500


@api_bp.route("/scheduler/resume", methods=["POST"])
@admin_required
def scheduler_resume():
    """POST /api/scheduler/resume — Resume scheduler (Sensitive)."""
    try:
        res = api_service.resume_scheduler()
        audit_repo.log_event("SCHEDULER", "RESUME_SCHEDULER", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Scheduler resumed via /api/scheduler/resume")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to resume scheduler: {e}", exc_info=True)
        audit_repo.log_event("SCHEDULER", "RESUME_SCHEDULER", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Failed to resume scheduler")
        return jsonify({"status": "failed", "error": "Failed to resume scheduler. Check server logs."}), 500


@api_bp.route("/scheduler/restart", methods=["POST"])
@admin_required
def scheduler_restart():
    """POST /api/scheduler/restart — Restart scheduler (Sensitive)."""
    try:
        res = api_service.restart_scheduler()
        audit_repo.log_event("SCHEDULER", "RESTART_SCHEDULER", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Scheduler restarted via /api/scheduler/restart")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to restart scheduler: {e}", exc_info=True)
        audit_repo.log_event("SCHEDULER", "RESTART_SCHEDULER", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Failed to restart scheduler")
        return jsonify({"success": False, "status": "failed", "error": "Failed to restart scheduler. Check server logs."}), 500


@api_bp.route("/report/trigger", methods=["POST"])
@admin_required
def trigger_daily_report():
    """POST /api/report/trigger — Send Daily Report Now (Sensitive)."""
    try:
        res = api_service.send_daily_report_now()
        audit_repo.log_event("REPORTS", "TRIGGER_REPORT", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Daily report triggered via /api/report/trigger")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to trigger daily report: {e}", exc_info=True)
        audit_repo.log_event("REPORTS", "TRIGGER_REPORT", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Failed to trigger daily report")
        return jsonify({"success": False, "status": "failed", "error": "Failed to trigger daily report. Check server logs."}), 500


@api_bp.route("/opportunities/clear-old", methods=["POST"])
@admin_required
def clear_old_opportunities():
    """POST /api/opportunities/clear-old — Clear Old Opportunities (Sensitive)."""
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
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to clear old opportunities: {e}", exc_info=True)
        audit_repo.log_event("OPPORTUNITIES", "CLEAR_OLD", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Failed to clear old opportunities")
        return jsonify({"success": False, "status": "failed", "error": "Failed to clear old opportunities. Check server logs."}), 500


@api_bp.route("/analytics/refresh", methods=["POST"])
@admin_required
def refresh_analytics():
    """POST /api/analytics/refresh — Refresh Analytics (Sensitive)."""
    try:
        res = api_service.refresh_analytics()
        audit_repo.log_event("ANALYTICS", "REFRESH", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Analytics refreshed via /api/analytics/refresh")
        resp = jsonify(res)
        resp.headers["Deprecation"] = "true"
        return resp
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to refresh analytics: {e}", exc_info=True)
        audit_repo.log_event("ANALYTICS", "REFRESH", "FAILED", username=session.get("admin_username"), source_ip=get_client_ip(request), details="Failed to refresh analytics")
        return jsonify({"success": False, "status": "failed", "error": "Failed to refresh analytics. Check server logs."}), 500


@api_bp.route("/me", methods=["GET"])
def get_current_user_profile():
    """
    GET /api/me ? Returns current session state and display identity.
    Internal account identifiers are not exposed to the client.
    Returns HTTP 200 with authenticated=False if unauthenticated so SPA can bootstrap smoothly.
    """
    user_id = session.get("user_id") or session.get("admin_user_id")
    is_admin = bool(session.get("admin_authenticated"))
    is_auth = bool(user_id or is_admin)

    if not is_auth:
        return jsonify({
            "authenticated": False,
            "user": None,
        }), 200

    username = session.get("username") or session.get("admin_username")
    email = session.get("email")
    role = session.get("admin_role") or session.get("role", "Viewer")

    return jsonify({
        "authenticated": True,
        "user": {
            "username": username,
            "email": email,
            "role": role,
            **({"is_admin": True} if is_admin else {}),
        },
    }), 200


@api_bp.route("/opportunities/saved", methods=["GET"])
@login_required
def get_saved_opportunities_api():
    """GET /api/opportunities/saved — Return saved opportunities for current user."""
    user_id = session.get("user_id") or session.get("admin_user_id")
    from src.models.query_filter_dto import QueryFilterDTO
    filter_dto = QueryFilterDTO(
        user_id=str(user_id) if user_id else None,
        saved_only=True,
        page=1,
        per_page=50,
    )
    opp_service = OpportunityService()
    try:
        paginated = opp_service.search_opportunities(filter_dto)
        items = [dataclasses.asdict(item) if dataclasses.is_dataclass(item) else dict(item) for item in paginated.items]
        return jsonify({"status": "success", "opportunities": items, "total": paginated.total_count})
    except Exception as e:
        logger.error(f"Error fetching saved opportunities: {e}")
        return jsonify({"status": "success", "opportunities": [], "total": 0})


@api_bp.route("/opportunities/<opportunity_id>", methods=["GET"])
@login_required
def get_opportunity_detail_api(opportunity_id: str):
    """GET /api/opportunities/<opportunity_id> — Return opportunity detail as JSON."""
    user_id = session.get("user_id") or session.get("admin_user_id")
    opp_service = OpportunityService()
    try:
        dto = opp_service.get_opportunity_detail(opportunity_id, user_id=str(user_id) if user_id else None)
    except Exception:
        dto = None

    if dto:
        opp_dict = dataclasses.asdict(dto)
        return jsonify({"status": "success", "opportunity": opp_dict})

    opp_repo = OpportunityRepository(db_manager=get_db_manager())
    raw_opp = opp_repo.read_by_id(opportunity_id)
    if not raw_opp:
        return jsonify({"status": "error", "error": "Opportunity not found"}), 404

    opp_dict = raw_opp.to_dict() if hasattr(raw_opp, "to_dict") else dict(raw_opp)
    return jsonify({"status": "success", "opportunity": opp_dict})


@api_bp.route("/notifications", methods=["GET"])
@login_required
def get_notifications_api():
    """GET /api/notifications — Retrieve notifications for the current authenticated user."""
    user_id = session.get("user_id") or session.get("admin_user_id")
    if not user_id:
        return jsonify({"status": "failed", "error": "Authentication required"}), 401

    notif_repo = NotificationRepository(db_manager=get_db_manager())
    notifications = notif_repo.get_user_notifications(user_id=str(user_id), limit=50)
    unread_count = sum(1 for n in notifications if not n.get("is_read"))

    formatted_notifs = []
    for n in notifications:
        item = dict(n)
        if "id" in item:
            item["id"] = str(item["id"])
        if "created_at" in item and item["created_at"]:
            item["created_at"] = str(item["created_at"])
        formatted_notifs.append(item)

    return jsonify({
        "status": "success",
        "notifications": formatted_notifs,
        "unread_count": unread_count,
    })


@api_bp.route("/insights", methods=["GET"])
@login_required
def get_insights_api():
    """GET /api/insights — Retrieve user intelligence and private opportunity insights."""
    user_id = session.get("user_id") or session.get("admin_user_id")
    insights = analytics_service.get_user_intelligence(user_id=user_id)
    if dataclasses.is_dataclass(insights):
        insights_data = dataclasses.asdict(insights)
    elif hasattr(insights, "to_dict"):
        insights_data = insights.to_dict()
    else:
        insights_data = insights
    return jsonify({"status": "success", "insights": insights_data})


@api_bp.route("/quality/stats", methods=["GET"])
@login_required
def get_quality_stats_api():
    """GET /api/quality/stats — Quality overview statistics."""
    opp_repo = OpportunityRepository(db_manager=get_db_manager())
    try:
        stats = opp_repo.get_quality_stats()
    except Exception:
        stats = {
            "accepted_count": 0,
            "rejected_count": 0,
            "avg_confidence": 0.0,
            "avg_quality": 0.0,
            "top_rejection_reasons": {},
        }
    return jsonify({"status": "success", "stats": stats})


