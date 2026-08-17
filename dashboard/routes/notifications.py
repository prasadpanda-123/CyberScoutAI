"""
User Notifications Route for CyberScout AI.
"""

from flask import Blueprint, render_template, session
from src.auth.decorators import login_required
from src.database.connection import DatabaseManager
from src.database.scheduler_repository import SchedulerRepository

notifications_bp = Blueprint("notifications_ui", __name__)


@notifications_bp.route("/notifications")
@login_required
def index():
    """Renders user-facing notification preferences and daily intelligence status."""
    db_mgr = DatabaseManager()
    sched_repo = SchedulerRepository(db_manager=db_mgr)
    state = sched_repo.get_state()

    user_email = session.get("email") or "Registered Email"

    email_info = {
        "status": "Active",
        "frequency": "Daily at 00:00 UTC",
        "recipient_email": user_email,
        "last_delivery": state.get("last_email_sent") or "Active (Awaiting next scheduled cycle)",
        "attachments": "DOCX & CSV Daily Opportunity Digests",
    }
    return render_template(
        "notifications.html",
        active_page="notifications",
        email_info=email_info,
    )
