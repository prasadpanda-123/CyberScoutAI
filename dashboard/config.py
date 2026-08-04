"""
Configuration settings for Flask Web Dashboard.
"""

import os
from pathlib import Path


class DashboardConfig:
    """Flask application configuration settings."""

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        os.environ.get("FLASK_SECRET_KEY", "cyberscout-ai-v1-1-secret-key-2026"),
    )
    DEBUG = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    TESTING = False
    PORT = int(os.environ.get("PORT", 5000))
    HOST = "0.0.0.0"
    APP_ENV = os.environ.get("APP_ENV", "production")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    JSON_SORT_KEYS = False
