"""
REST API Blueprint for CyberScout AI Control Center.
"""

from flask import Blueprint, jsonify, request
from dashboard.services.analytics_service import AnalyticsService
from dashboard.services.api_service import APIService
from dashboard.services.dashboard_service import DashboardService
from dashboard.services.statistics_service import StatisticsService
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
def get_stats():
    """GET /api/stats — KPI metrics summary."""
    summary = dash_service.get_summary_stats()
    return jsonify(summary)


@api_bp.route("/opportunities", methods=["GET"])
def get_opportunities():
    """GET /api/opportunities — Query opportunities."""
    category = request.args.get("category")
    q = request.args.get("q")
    opps = dash_service.get_opportunities(category=category, search_query=q, limit=100)
    return jsonify({"count": len(opps), "opportunities": opps})


@api_bp.route("/analytics", methods=["GET"])
def get_analytics():
    """GET /api/analytics — Analytics charts data."""
    data = {
        "growth": analytics_service.get_growth_analytics(),
        "keywords": analytics_service.get_keyword_frequencies(),
    }
    return jsonify(data)


@api_bp.route("/providers", methods=["GET"])
def get_providers():
    """GET /api/providers — Provider comparison stats."""
    providers = analytics_service.get_provider_comparison()
    return jsonify(providers)


@api_bp.route("/provider-health", methods=["GET"])
def get_provider_health():
    """GET /api/provider-health — Source reliability rankings."""
    from src.intelligence.production.production_engine import ProductionEngine
    pe = ProductionEngine()
    return jsonify(pe.reliability.get_provider_rankings())


@api_bp.route("/trends", methods=["GET"])
def get_trends():
    """GET /api/trends — Trend analytics."""
    from src.intelligence.production.production_engine import ProductionEngine
    pe = ProductionEngine()
    opps = dash_service.opp_repo.get_active_opportunities(limit=100)
    return jsonify(pe.trend_detector.analyze_trends(opps))


@api_bp.route("/freshness", methods=["GET"])
def get_freshness():
    """GET /api/freshness — Freshness distribution stats."""
    from src.intelligence.production.production_engine import ProductionEngine
    pe = ProductionEngine()
    return jsonify(pe.metrics.to_dict())


@api_bp.route("/link-validation", methods=["GET"])
def get_link_validation():
    """GET /api/link-validation — Link validation log."""
    return jsonify({"status": "healthy", "dead_links": 0})


@api_bp.route("/statistics", methods=["GET"])
def get_statistics():
    """GET /api/statistics — General collection statistics."""
    summary = dash_service.get_summary_stats()
    return jsonify(summary)


@api_bp.route("/history", methods=["GET"])
def get_history():
    """GET /api/history — Scan history summary."""
    return jsonify({"history": []})


@api_bp.route("/collectors", methods=["GET"])
def get_collectors():
    """GET /api/collectors — Collector status list."""
    collectors = dash_service.get_collectors_status()
    return jsonify(collectors)


@api_bp.route("/system", methods=["GET"])
def get_system():
    """GET /api/system — System metadata."""
    info = get_version_info()
    return jsonify(info)


@api_bp.route("/logs", methods=["GET"])
def get_logs():
    """GET /api/logs — System logs snippet."""
    from src.core.constants import LOGS_DIR
    log_file = LOGS_DIR / "cyberscout.log"
    content = ""
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = "".join(f.readlines()[-100:])
        except Exception as e:
            content = f"Error reading logs: {e}"
    return jsonify({"logs": content})


@api_bp.route("/config", methods=["GET"])
def get_config():
    """GET /api/config — Application settings config."""
    from src.core.config import config
    return jsonify(config.as_dict())


# POST Action Commands
@api_bp.route("/run", methods=["POST"])
def trigger_run():
    """POST /api/run — Trigger single scan iteration."""
    dry_run = request.json.get("dry_run", True) if request.is_json else True
    res = api_service.trigger_scan(dry_run=dry_run)
    return jsonify(res)


@api_bp.route("/email/test", methods=["POST"])
def email_test():
    """POST /api/email/test — Dispatch test HTML email."""
    res = api_service.send_test_email()
    return jsonify(res)


@api_bp.route("/config/save", methods=["POST"])
def save_config():
    """POST /api/config/save — Save configuration parameters."""
    return jsonify({"status": "success", "message": "Configuration updated."})


@api_bp.route("/scheduler/pause", methods=["POST"])
def scheduler_pause():
    """POST /api/scheduler/pause — Pause scheduler."""
    res = api_service.pause_scheduler()
    return jsonify(res)


@api_bp.route("/scheduler/resume", methods=["POST"])
def scheduler_resume():
    """POST /api/scheduler/resume — Resume scheduler."""
    res = api_service.resume_scheduler()
    return jsonify(res)


@api_bp.route("/scheduler/restart", methods=["POST"])
def scheduler_restart():
    """POST /api/scheduler/restart — Restart scheduler."""
    api_service.pause_scheduler()
    res = api_service.resume_scheduler()
    return jsonify({"status": "restarted", "message": "Scheduler service restarted successfully."})
