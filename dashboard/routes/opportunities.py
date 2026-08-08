"""
Opportunities Page Routes (Page 2).
"""

from flask import Blueprint, render_template, request
from dashboard.services.dashboard_service import DashboardService
from src.auth.decorators import login_required

opportunities_bp = Blueprint("opportunities_ui", __name__)
dash_service = DashboardService()


@opportunities_bp.route("/opportunities")
@login_required
def index():
    """Renders Opportunities table view."""
    category = request.args.get("category", "all")
    search_q = request.args.get("q", "")
    try:
        opps = dash_service.get_opportunities(category=category, search_query=search_q, limit=100)
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to fetch opportunities for route /opportunities: {e}")
        opps = []

    return render_template(
        "opportunities.html",
        active_page="opportunities",
        opportunities=opps,
        selected_category=category,
        search_query=search_q,
    )

