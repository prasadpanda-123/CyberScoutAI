"""
Configuration settings for Flask Web Dashboard.
"""

import os
from pathlib import Path

class DashboardConfig:
    """Flask application configuration settings."""

    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "cyberscout-ai-v1-1-secret-key-2026")
    DEBUG = False
    TESTING = False
    PORT = 5000
    HOST = "127.0.0.1"
    JSON_SORT_KEYS = False
