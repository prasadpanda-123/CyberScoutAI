"""
Unit tests for Secure GitHub Token Integration.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from src.collectors.http_client import HTTPClient, sanitize_secret_text
from src.core.health import HealthMonitor
from src.main import get_github_status


class TestGitHubTokenIntegration(unittest.TestCase):
    """Tests secure GitHub token handling, header injection, and secret redaction."""

    def test_sanitize_secret_text_redacts_tokens(self):
        """Verify token strings and Bearer headers are redacted."""
        raw = "Error sending token ghp_1234567890abcdefghijklmnopqrstuvwxyz with Bearer ghp_secret"
        cleaned = sanitize_secret_text(raw)
        self.assertNotIn("ghp_1234567890abcdefghijklmnopqrstuvwxyz", cleaned)
        self.assertIn("[REDACTED]", cleaned)

    @patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_mock_secret_token_12345"})
    def test_github_token_header_injection(self):
        """Verify Authorization header is injected when GITHUB_TOKEN is present."""
        client = HTTPClient()
        with patch.object(client.session, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "ok"}'
            mock_get.return_value = mock_response

            client.get("https://api.github.com/search/repositories?q=cybersecurity_test_query", use_cache=False)

            args, kwargs = mock_get.call_args
            req_headers = kwargs.get("headers", {})
            self.assertEqual(req_headers.get("Authorization"), "Bearer ghp_mock_secret_token_12345")
            self.assertEqual(req_headers.get("Accept"), "application/vnd.github+json")
            self.assertEqual(req_headers.get("X-GitHub-Api-Version"), "2022-11-28")

    @patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True)
    def test_github_anonymous_mode(self):
        """Verify requests fall back to anonymous mode when token is absent."""
        client = HTTPClient()
        with patch.object(client.session, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "ok"}'
            mock_get.return_value = mock_response

            client.get("https://api.github.com/search/repositories?q=cybersecurity_test_query", use_cache=False)

            args, kwargs = mock_get.call_args
            req_headers = kwargs.get("headers", {})
            self.assertNotIn("Authorization", req_headers)
            self.assertEqual(req_headers.get("Accept"), "application/vnd.github+json")

    @patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test_token_999"})
    def test_github_status_cli_authenticated(self):
        """Verify get_github_status() formats authenticated response dictionary."""
        with patch("src.collectors.http_client.HTTPClient.get") as mock_get:
            mock_get.return_value = (200, '{"resources": {"core": {"limit": 5000, "remaining": 4995, "reset": 1700000000}, "search": {"limit": 30}}}')
            status = get_github_status()
            self.assertTrue(status["authenticated"])
            self.assertEqual(status["mode"], "Authenticated")
            self.assertEqual(status["core_limit"], 5000)
            self.assertEqual(status["rate_limit_remaining"], 4995)

    @patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True)
    def test_github_status_cli_anonymous(self):
        """Verify get_github_status() formats anonymous response dictionary."""
        with patch("src.collectors.http_client.HTTPClient.get") as mock_get:
            mock_get.return_value = (200, '{"resources": {"core": {"limit": 60, "remaining": 55, "reset": 1700000000}, "search": {"limit": 10}}}')
            status = get_github_status()
            self.assertFalse(status["authenticated"])
            self.assertEqual(status["mode"], "Anonymous Mode")
            self.assertEqual(status["core_limit"], 60)

    @patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_valid_token"})
    def test_health_monitor_github_api_check(self):
        """Verify HealthMonitor includes GitHub API check."""
        monitor = HealthMonitor()
        res = monitor.check_github_api()
        self.assertEqual(res.component, "github_api")
        self.assertTrue(res.status)
        self.assertEqual(res.details["mode"], "Authenticated")


if __name__ == "__main__":
    unittest.main()
