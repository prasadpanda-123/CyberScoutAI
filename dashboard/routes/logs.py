"""
Log Control Center Route (Page 9).
"""

from flask import Blueprint, render_template, request
from src.database.log_repository import LogRepository

logs_bp = Blueprint("logs_ui", __name__)
log_repo = LogRepository()


@logs_bp.route("/logs")
def index():
    """Renders persistent structured log control center page."""
    level = request.args.get("level", "ALL")
    module = request.args.get("module", "ALL")
    search_q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))

    query_res = log_repo.query_logs(
        level=level,
        module=module,
        search_query=search_q,
        page=page,
        limit=limit,
    )
    stats = log_repo.get_log_stats()

    return render_template(
        "logs.html",
        active_page="logs",
        logs=query_res.get("logs", []),
        pagination=query_res,
        stats=stats,
        selected_level=level,
        selected_module=module,
        search_query=search_q,
    )
