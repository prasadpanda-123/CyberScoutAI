from flask import Blueprint, redirect, url_for
from src.auth.decorators import admin_required

collectors_bp = Blueprint("collectors_ui", __name__)


@collectors_bp.route("/collectors")
@admin_required
def index():
    """Redirects legacy /collectors to protected /admin/collectors."""
    return redirect(url_for("admin_ui.admin_collectors"))

