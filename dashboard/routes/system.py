"""
System Specifications and Diagnostics Routes (Page 11 & Diagnostics).
"""

from flask import Blueprint, render_template
from src.core.rss_diagnostics import RSSDiagnosticsManager
from src.core.version import get_version_info

system_bp = Blueprint("system_ui", __name__)


@system_bp.route("/system")
def index():
    """Renders System & Environment Information page."""
    version_info = get_version_info()
    sys_specs = {
        "app_name": version_info.get("app_name", "CyberScout AI"),
        "version": version_info.get("version", "1.1.3"),
        "build_date": version_info.get("build_date", "2026-08-03"),
        "python_version": version_info.get("python_version", "3.12.10"),
        "platform": version_info.get("platform", "Windows-11"),
        "git_tag": "v1.1.3-command-docs-ready",
        "sqlite_version": "3.45.1",
        "uptime": "Active",
    }
    return render_template(
        "system.html",
        active_page="system",
        sys_specs=sys_specs,
    )


@system_bp.route("/diagnostics")
@system_bp.route("/system-diagnostics")
def system_diagnostics():
    """Renders System & Feed Diagnostics Control page."""
    diag_summary = RSSDiagnosticsManager().get_feed_diagnostics_summary()
    return render_template(
        "system_diagnostics.html",
        active_page="diagnostics",
        diag=diag_summary,
    )
