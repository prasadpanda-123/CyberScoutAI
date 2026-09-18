"""
Phase 7 Unit Tests: Production Security & Deployment Audit Verification.

Verifies:
1. Environment configuration: APP_ENV=production and SESSION_COOKIE_SECURE handling.
2. DOM XSS defense-in-depth: logs.html template escapes dynamic parameters.
3. Strict CSP headers remain enforced across all endpoints.
4. Administrative session hardening: HttpOnly, SameSite, Secure cookie options.
"""

import os
import unittest
from unittest.mock import patch
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestPhase7AuditHardening(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    def test_logs_template_contains_escape_html_helper(self):
        """Verify dashboard/templates/logs.html implements escapeHtml to prevent DOM injection."""
        logs_template_path = os.path.join(self.repo_root, "dashboard", "templates", "logs.html")
        with open(logs_template_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("function escapeHtml(str)", content)
        self.assertIn("escapeHtml(log.message)", content)
        self.assertIn("escapeHtml(log.module)", content)
        self.assertIn("escapeHtml(log.exception_text)", content)

    def test_production_environment_cookie_security_flag(self):
        """Verify APP_ENV=production properly enables SESSION_COOKIE_SECURE when flag is true."""
        with patch.dict(os.environ, {"APP_ENV": "production", "SESSION_COOKIE_SECURE": "true"}):
            app = create_app()
            self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
            self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
            self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_dev_environment_cookie_security_flag_remains_false(self):
        """Verify development defaults do not require HTTPS cookie flags if not in production."""
        with patch.dict(os.environ, {"APP_ENV": "development", "SESSION_COOKIE_SECURE": "false"}):
            app = create_app()
            self.assertFalse(app.config["SESSION_COOKIE_SECURE"])

    def test_csp_strict_protection_on_admin_and_public(self):
        """Verify strict CSP headers on both public and admin routes."""
        for path in ["/", "/login", "/admin/login"]:
            res = self.client.get(path)
            csp = res.headers.get("Content-Security-Policy", "")
            self.assertIn("script-src 'self' 'nonce-", csp)
            self.assertNotIn("'unsafe-inline'", csp.split("script-src")[1].split(";")[0])
            self.assertNotIn("'unsafe-eval'", csp)
            self.assertIn("object-src 'none'", csp)
            self.assertIn("frame-ancestors 'none'", csp)


if __name__ == "__main__":
    unittest.main()
