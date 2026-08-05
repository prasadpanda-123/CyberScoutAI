"""
Scheduler Management Route (Page 5).
"""

from flask import Blueprint, render_template
from dashboard.services.api_service import APIService
from src.auth.decorators import login_required, roles_required

scheduler_bp = Blueprint("scheduler_ui", __name__)
api_service = APIService()


@scheduler_bp.route("/scheduler")
@login_required
@roles_required("Super Admin", "Administrator")
def index():
    """Renders Scheduler control dashboard page."""
    sched_status = api_service.get_scheduler_status()
    return render_template(
        "scheduler.html",
        active_page="scheduler",
        scheduler_status=sched_status,
    )
