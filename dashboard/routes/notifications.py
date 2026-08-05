"""
Notifications Route (Page 6).
"""

from flask import Blueprint, render_template
from src.auth.decorators import login_required, roles_required

notifications_bp = Blueprint("notifications_ui", __name__)


@notifications_bp.route("/notifications")
@login_required
@roles_required("Super Admin", "Administrator")
def index():
    """Renders Notifications control & preview page."""
    email_info = {
        "last_email": "Daily Scheduled",
        "last_status": "Success",
        "recipient_count": 1,
        "smtp_host": "Brevo REST API (HTTPS)",
    }
    return render_template(
        "notifications.html",
        active_page="notifications",
        email_info=email_info,
    )
