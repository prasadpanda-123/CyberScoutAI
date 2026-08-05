"""
REST API Blueprint for CyberScout AI Control Center.
"""

from flask import Blueprint, jsonify, request, send_from_directory, Response
import json
from dashboard.services.analytics_service import AnalyticsService
from dashboard.services.api_service import APIService
from dashboard.services.dashboard_service import DashboardService
from dashboard.services.statistics_service import StatisticsService
from src.auth.decorators import login_required, roles_required
from src.core.constants import REPORTS_DIR
from src.core.version import get_version_info

api_bp = Blueprint("api", __name__, url_prefix="/api")

dash_service = DashboardService()
stats_service = StatisticsService()
analytics_service = AnalyticsService()
api_service = APIService()


@api_bp.route("/health", methods=["GET"])
def get_health():
    """GET /api/health — System health check."""
    report = dash_service.get_health_report()
    return jsonify(report)


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
@login_required
def get_collectors():
    """GET /api/dashboard/collectors — Collector status list."""
    collectors = dash_service.get_collectors_status()
    return jsonify(collectors)


@api_bp.route("/dashboard/reports", methods=["GET"])
@api_bp.route("/reports", methods=["GET"])
@login_required
def get_reports():
    """GET /api/dashboard/reports — List of generated DOCX & CSV reports."""
    reports = api_service.get_reports_list()
    return jsonify({"count": len(reports), "reports": reports})


@api_bp.route("/system", methods=["GET"])
@login_required
def get_system():
    """GET /api/system — System metadata."""
    info = get_version_info()
    return jsonify(info)


@api_bp.route("/system/smtp-health", methods=["GET"])
@api_bp.route("/email/health", methods=["GET"])
@login_required
def get_smtp_health():
    """GET /api/system/smtp-health — Returns email provider pre-flight diagnostics."""
    res = api_service.check_smtp_health()
    return jsonify(res)


@api_bp.route("/logs", methods=["GET"])
@api_bp.route("/dashboard/logs", methods=["GET"])
@login_required
@roles_required("Super Admin")
def get_logs():
    """GET /api/dashboard/logs — Structured AppLogs with level/module/search filters and pagination."""
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


@api_bp.route("/logs/export", methods=["GET"])
@login_required
@roles_required("Super Admin")
def export_logs():
    """GET /api/logs/export — Export logs in JSON format."""
    data = api_service.get_logs(limit=1000)
    json_bytes = json.dumps(data.get("logs", []), indent=2).encode("utf-8")
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=cyberscout_logs.json"},
    )


@api_bp.route("/config", methods=["GET"])
@login_required
@roles_required("Super Admin")
def get_config():
    """GET /api/config — Application settings config."""
    from src.core.config import config
    return jsonify(config.as_dict())


# POST Action Commands with JSON error safety and RBAC
@api_bp.route("/run", methods=["POST"])
@login_required
@roles_required("Super Admin", "Administrator")
def trigger_run():
    """POST /api/run — Trigger single scan iteration."""
    try:
        dry_run = False
        if request.is_json and request.json:
            dry_run = bool(request.json.get("dry_run", False))
        res = api_service.trigger_scan(dry_run=dry_run)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "status": "failed", "error": str(e)})


@api_bp.route("/email/test", methods=["POST"])
@login_required
@roles_required("Super Admin", "Administrator")
def email_test():
    """POST /api/email/test — Dispatch test HTML email."""
    try:
        res = api_service.send_test_email()
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)})


@api_bp.route("/scheduler/pause", methods=["POST"])
@login_required
@roles_required("Super Admin", "Administrator")
def scheduler_pause():
    """POST /api/scheduler/pause — Pause scheduler."""
    try:
        res = api_service.pause_scheduler()
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)})


@api_bp.route("/scheduler/resume", methods=["POST"])
@login_required
@roles_required("Super Admin", "Administrator")
def scheduler_resume():
    """POST /api/scheduler/resume — Resume scheduler."""
    try:
        res = api_service.resume_scheduler()
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)})


@api_bp.route("/scheduler/restart", methods=["POST"])
@login_required
@roles_required("Super Admin", "Administrator")
def scheduler_restart():
    """POST /api/scheduler/restart — Restart scheduler."""
    try:
        api_service.pause_scheduler()
        res = api_service.resume_scheduler()
        return jsonify({"status": "restarted", "message": "Scheduler service restarted successfully."})
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)})
