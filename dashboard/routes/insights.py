"""
User Personal Intelligence & Private Opportunity Insights Route.

Renders private user analytics including saved opportunity urgency, search history,
preference alignment, and notification metrics under strict tenant isolation.
"""

from flask import Blueprint, redirect, render_template, session, url_for
from dashboard.services.analytics_service import AnalyticsService
from src.auth.decorators import login_required

insights_bp = Blueprint("insights_ui", __name__)
analytics_service = AnalyticsService()


@insights_bp.route("/insights", methods=["GET"])
@login_required
def index():
    """Renders the private User Intelligence dashboard."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth_ui.login"))

    import uuid
    try:
        clean_uid = str(uuid.UUID(str(user_id).strip()))
    except (ValueError, TypeError, AttributeError):
        session.clear()
        return redirect(url_for("auth_ui.login"))

    insights = analytics_service.get_user_intelligence(user_id=clean_uid)

    return render_template(
        "insights.html",
        active_page="insights",
        insights=insights,
        user_id=user_id,
    )
