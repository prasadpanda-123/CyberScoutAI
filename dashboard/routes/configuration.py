"""
Configuration Management Route (Page 8).
"""

from pathlib import Path
from flask import Blueprint, render_template
import yaml

from src.auth.decorators import login_required, roles_required
from src.core.constants import CONFIG_DIR

configuration_bp = Blueprint("configuration_ui", __name__)


@configuration_bp.route("/configuration")
@login_required
@roles_required("Super Admin")
def index():
    """Renders YAML Configuration editor page."""
    configs = {}
    for yaml_file in CONFIG_DIR.glob("*.yaml"):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                configs[yaml_file.name] = f.read()
        except Exception:
            configs[yaml_file.name] = "# Error reading file"

    return render_template(
        "configuration.html",
        active_page="configuration",
        configs=configs,
    )
