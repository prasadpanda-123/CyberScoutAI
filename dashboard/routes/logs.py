"""
Log Viewer Route (Page 9).
"""

from pathlib import Path
from flask import Blueprint, render_template, request
from src.core.constants import LOGS_DIR

logs_bp = Blueprint("logs_ui", __name__)


@logs_bp.route("/logs")
def index():
    """Renders log viewer page."""
    log_file = LOGS_DIR / "cyberscout.log"
    log_lines = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log_lines = f.readlines()[-300:]  # Last 300 lines
        except Exception:
            log_lines = ["Could not read log file."]

    level_filter = request.args.get("level", "ALL").upper()
    if level_filter != "ALL":
        log_lines = [line for line in log_lines if f"[{level_filter}]" in line or f"- {level_filter} -" in line]

    return render_template(
        "logs.html",
        active_page="logs",
        log_lines="".join(log_lines),
        selected_level=level_filter,
    )
