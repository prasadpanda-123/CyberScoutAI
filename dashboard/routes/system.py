from flask import Blueprint, redirect, url_for
from src.auth.decorators import admin_required

system_bp = Blueprint("system_ui", __name__)


@system_bp.route("/system")
@admin_required
def index():
    """Redirects legacy /system to protected /admin/system."""
    return redirect(url_for("admin_ui.admin_system"))


@system_bp.route("/diagnostics")
@system_bp.route("/system-diagnostics")
@admin_required
def system_diagnostics():
    """Redirects legacy /diagnostics to protected /admin/diagnostics."""
    return redirect(url_for("admin_ui.admin_diagnostics"))

