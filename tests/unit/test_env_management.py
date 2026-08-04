"""
Unit tests for Local Environment File (.env) Integration.
"""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.collectors.http_client import sanitize_secret_text
from src.core.bootstrap import ensure_env_file
from src.main import get_env_status_report


class TestEnvironmentManagement(unittest.TestCase):
    """Tests local environment file loading, auto-generation, and secret redaction."""

    def test_ensure_env_file_auto_creates_from_example(self):
        """Verify .env is copied from .env.example when missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            example_file = tmp_root / ".env.example"
            env_file = tmp_root / ".env"

            example_file.write_text("APP_ENV=development\nGITHUB_TOKEN=\nSMTP_PASSWORD=\n", encoding="utf-8")
            self.assertFalse(env_file.exists())

            created = ensure_env_file(root_dir=tmp_root)
            self.assertTrue(created)
            self.assertTrue(env_file.exists())
            self.assertIn("APP_ENV=development", env_file.read_text(encoding="utf-8"))

    def test_ensure_env_file_graceful_when_missing(self):
        """Verify ensure_env_file handles directory with no .env or .env.example gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            created = ensure_env_file(root_dir=tmp_root)
            self.assertTrue(created)  # load_dotenv executed without error

    @patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_secret_token_12345", "SMTP_PASSWORD": "super_secret_smtp_password"})
    def test_secret_redaction(self):
        """Verify secrets are masked in error outputs."""
        log_msg = "Error connecting with GITHUB_TOKEN ghp_secret_token_12345 and password super_secret_smtp_password"
        clean_msg = sanitize_secret_text(log_msg)
        self.assertNotIn("ghp_secret_token_12345", clean_msg)
        self.assertIn("[REDACTED]", clean_msg)

    def test_get_env_status_report(self):
        """Verify get_env_status_report returns formatted string."""
        report = get_env_status_report()
        self.assertIn("Environment Status", report)
        self.assertIn("Configuration ........ OK", report)
        self.assertIn("Application Mode", report)


if __name__ == "__main__":
    unittest.main()
