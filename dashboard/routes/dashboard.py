"""
Dashboard Overview Page Route (Page 1) & Reports Download Center.
"""

from flask import Blueprint, jsonify, render_template, request, send_from_directory, abort
from dashboard.services.api_service import APIService
from dashboard.services.dashboard_service import DashboardService
from dashboard.services.statistics_service import StatisticsService
from src.auth.decorators import login_required, roles_required
from src.core.constants import REPORTS_DIR
from src.core.version import get_version_info

dashboard_bp = Blueprint("dashboard_ui", __name__)
dash_service = DashboardService()
stats_service = StatisticsService()
api_service = APIService()


@dashboard_bp.route("/")
def landing():
    """Renders public CyberScout AI Landing Page."""
    return render_template("landing.html")


@dashboard_bp.route("/dashboard")
@login_required
def index():
    """Renders main Overview Dashboard page or returns JSON status info."""
    if (
        request.headers.get("Accept") == "application/json"
        or request.args.get("format") == "json"
    ):
        info = get_version_info()
        return jsonify({
            "status": "ok",
            "application": info.get("app_name", "CyberScout AI"),
            "version": info.get("version", "1.2.0"),
        }), 200

    summary = dash_service.get_summary_stats()
    cat_dist = stats_service.get_category_distribution()
    prio_dist = stats_service.get_priority_distribution()
    src_dist = stats_service.get_source_distribution()
    daily_trends = stats_service.get_daily_opportunity_trends()

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        summary=summary,
        category_distribution=cat_dist,
        priority_distribution=prio_dist,
        source_distribution=src_dist,
        daily_trends=daily_trends,
    )


@dashboard_bp.route("/reports")
@login_required
def reports_page():
    """Renders Reports Download Center page."""
    reports = api_service.get_reports_list()
    return render_template(
        "reports.html",
        active_page="reports",
        reports=reports,
    )


@dashboard_bp.route("/reports/download/<path:filename>")
@login_required
@roles_required("Super Admin", "Administrator", "Operator")
def download_report(filename):
    """Safely serves generated DOCX or CSV report files for download."""
    reports_dir = REPORTS_DIR
    if not reports_dir.exists():
        abort(404)
    return send_from_directory(str(reports_dir), filename, as_attachment=True)
