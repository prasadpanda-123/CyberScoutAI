from flask import Blueprint, redirect, url_for
from src.auth.decorators import admin_required

logs_bp = Blueprint("logs_ui", __name__)


@logs_bp.route("/logs")
@admin_required
def index():
    """Redirects legacy /logs to protected /admin/logs."""
    return redirect(url_for("admin_ui.admin_logs"))

