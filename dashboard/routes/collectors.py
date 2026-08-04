"""
Collectors Management Route (Page 4).
"""

from flask import Blueprint, render_template
from dashboard.services.dashboard_service import DashboardService

collectors_bp = Blueprint("collectors_ui", __name__)
dash_service = DashboardService()


@collectors_bp.route("/collectors")
def index():
    """Renders Collectors overview and control page."""
    collectors_list = dash_service.get_collectors_status()
    return render_template(
        "collectors.html",
        active_page="collectors",
        collectors=collectors_list,
    )
