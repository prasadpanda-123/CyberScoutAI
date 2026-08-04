"""
System Specifications Route (Page 11).
"""

from flask import Blueprint, render_template
from src.core.version import get_version_info

system_bp = Blueprint("system_ui", __name__)


@system_bp.route("/system")
def index():
    """Renders System & Environment Information page."""
    version_info = get_version_info()
    sys_specs = {
        "app_name": version_info.get("app_name", "CyberScout AI"),
        "version": version_info.get("version", "1.1.0"),
        "build_date": version_info.get("build_date", "2026-08-03"),
        "python_version": version_info.get("python_version", "3.12.10"),
        "platform": version_info.get("platform", "Windows-11"),
        "git_tag": "v1.1.0-dashboard",
        "sqlite_version": "3.45.1",
        "uptime": "24h 12m",
    }
    return render_template(
        "system.html",
        active_page="system",
        sys_specs=sys_specs,
    )
