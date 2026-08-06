from flask import Blueprint, redirect, url_for
from src.auth.decorators import admin_required

scheduler_bp = Blueprint("scheduler_ui", __name__)


@scheduler_bp.route("/scheduler")
@admin_required
def index():
    """Redirects legacy /scheduler to protected /admin/scheduler."""
    return redirect(url_for("admin_ui.admin_scheduler"))

