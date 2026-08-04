"""
Version metadata and banner utilities for CyberScout AI.
"""

from datetime import datetime
import platform
import sys
from typing import Dict

APP_NAME = "CyberScout AI"
APP_VERSION = "1.1.1"
APP_TAGLINE = "Never Miss a Cybersecurity Opportunity Again."
BUILD_DATE = "2026-08-03"


def get_version_info() -> Dict[str, str]:
    """Returns detailed version and environment platform metadata dictionary."""
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "tagline": APP_TAGLINE,
        "build_date": BUILD_DATE,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


def format_banner(env: str = "development", db_status: str = "CONNECTED", db_version: int = 1) -> str:
    """Formats a clean, professional startup banner string."""
    info = get_version_info()
    lines = [
        "=" * 60,
        f"  {info['app_name']} v{info['version']} (Build {info['build_date']})",
        f"  {info['tagline']}",
        "=" * 60,
        f"  Environment  : {env}",
        f"  Python       : {info['python_version']}",
        f"  Platform     : {info['platform']}",
        f"  Database     : SQLite v{db_version} ({db_status})",
        "=" * 60,
    ]
    return "\n".join(lines)
