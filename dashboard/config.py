"""
Configuration settings for Flask Web Dashboard.
"""

import os
from pathlib import Path


INSECURE_DEFAULT_SECRETS = {
    "cyberscout-ai-v1-1-secret-key-2026",
    "secret",
    "secret_key",
    "changeme",
    "admin",
    "default",
    "password",
}


class DashboardConfig:
    """Flask application configuration settings."""

    APP_ENV = os.environ.get("CYBERSCOUT_ENV") or os.environ.get("APP_ENV", "production")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    TESTING = False
    PORT = int(os.environ.get("PORT", 5000))
    HOST = "0.0.0.0"
    DATABASE_URL = os.environ.get("DATABASE_URL")
    JSON_SORT_KEYS = False
    TEMPLATES_AUTO_RELOAD = True
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB global request body limit (SEC-10)

    # Session cookie security defaults
    SESSION_COOKIE_NAME = "cyberscout_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @classmethod
    def get_secret_key(cls) -> str:
        """
        Validates and retrieves the SECRET_KEY (SEC-06).
        In production, fails closed (raises RuntimeError) if missing or using an insecure default.
        In development/testing, allows explicit development fallback.
        """
        raw_secret = os.environ.get("SECRET_KEY") or os.environ.get("FLASK_SECRET_KEY")
        env_val = os.environ.get("CYBERSCOUT_ENV") or os.environ.get("APP_ENV") or cls.APP_ENV
        is_prod = (env_val == "production") or bool(os.environ.get("RAILWAY_ENVIRONMENT"))

        if is_prod and not cls.TESTING:
            if not raw_secret or not raw_secret.strip():
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable "
                    "is missing in production. Application cannot start safely."
                )
            if raw_secret.strip() in INSECURE_DEFAULT_SECRETS or len(raw_secret.strip()) < 16:
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable "
                    "is set to a known insecure or weak default in production. Application cannot start safely."
                )
            return raw_secret.strip()

        # Isolated development / testing fallback
        return (raw_secret or "cyberscout-dev-isolated-local-test-key-2026").strip()

    # Dynamic property fallback for code accessing DashboardConfig.SECRET_KEY directly
    @property
    def SECRET_KEY(self):
        return self.get_secret_key()


get_secret_key = DashboardConfig.get_secret_key

