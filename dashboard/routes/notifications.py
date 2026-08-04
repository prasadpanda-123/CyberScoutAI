"""
Notifications Route (Page 6).
"""

from flask import Blueprint, render_template

notifications_bp = Blueprint("notifications_ui", __name__)


@notifications_bp.route("/notifications")
def index():
    """Renders Notifications control & preview page."""
    email_info = {
        "last_email": "2026-08-04 08:00:00",
        "last_status": "Success",
        "recipient_count": 1,
        "smtp_host": "smtp.gmail.com",
    }
    return render_template(
        "notifications.html",
        active_page="notifications",
        email_info=email_info,
    )
