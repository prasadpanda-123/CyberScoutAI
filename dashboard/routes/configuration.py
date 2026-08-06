from flask import Blueprint, redirect, url_for
from src.auth.decorators import admin_required

configuration_bp = Blueprint("configuration_ui", __name__)


@configuration_bp.route("/configuration")
@admin_required
def index():
    """Redirects legacy /configuration to protected /admin/configuration."""
    return redirect(url_for("admin_ui.admin_configuration"))

