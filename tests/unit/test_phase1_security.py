"""
Comprehensive Security and Regression Tests for Phase 1:
Secure Web Control Surface & Service Boundary Foundation.

Tests:
1. Configuration secret redaction on /api/config and /admin/api/config.
2. Direct sanitize_config_dict() behavior with complex nested payloads and connection URIs.
3. RBAC and unauthenticated access control enforcement.
4. CSRF protection on state-changing administrative operations.
5. Explicit operational service boundary calls via APIService without CLI/subprocess invocation.
"""

import re
import unittest
from unittest.mock import MagicMock, patch

from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.core.config import sanitize_config_dict


class TestPhase1Security(unittest.TestCase):

    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    # -------------------------------------------------------------------------
    # 1. Direct Unit Tests for sanitize_config_dict
    # -------------------------------------------------------------------------

    def test_sanitize_config_dict_redacts_sensitive_keys(self):
        """Verify sanitize_config_dict redacts all secret-like keys and connection strings."""
        dirty_config = {
            "app_env": "production",
            "logging": {"level": "INFO", "file": "logs/app.log"},
            "database": {
                "provider": "postgresql",
                "url": "postgresql://postgres_user:SuperSecretPassword123!@db.example.com:5432/cyberscout_db",
            },
            "credentials": {
                "smtp_password": "my_email_password",
                "api_key": "live_api_key_value_xyz",
                "otp_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            },
            "third_party": {
                "brevo_api_key": "xkeysib-1234567890abcdef",
                "github_token": "ghp_PersonalAccessToken12345",
                "scheduler_secret": "long_random_scheduler_hmac_secret",
            },
            "nested_list": [
                {"secret_token": "token_abc"},
                {"public_item": "visible_data"},
                "postgresql://admin:hunter2@db.internal:5432/secrets",
            ],
        }

        clean = sanitize_config_dict(dirty_config)

        # Non-sensitive keys remain unchanged
        self.assertEqual(clean["app_env"], "production")
        self.assertEqual(clean["logging"]["level"], "INFO")
        self.assertEqual(clean["database"]["provider"], "postgresql")
        self.assertEqual(clean["nested_list"][1]["public_item"], "visible_data")

        # Database connection strings are masked
        self.assertEqual(clean["database"]["url"], "postgresql://user:******@host:port/dbname")
        self.assertNotIn("SuperSecretPassword123!", str(clean))
        self.assertNotIn("postgres_user", str(clean))

        # Credentials & secrets are redacted to '******'
        self.assertEqual(clean["credentials"]["smtp_password"], "******")
        self.assertEqual(clean["credentials"]["api_key"], "******")
        self.assertEqual(clean["credentials"]["otp_hash"], "******")
        self.assertEqual(clean["third_party"]["brevo_api_key"], "******")
        self.assertEqual(clean["third_party"]["github_token"], "******")
        self.assertEqual(clean["third_party"]["scheduler_secret"], "******")
        self.assertEqual(clean["nested_list"][0]["secret_token"], "******")
        self.assertIn("******", clean["nested_list"][2])

        # Assert no sensitive strings leaked anywhere in serialized output
        dumped = str(clean)
        for leak in [
            "SuperSecretPassword123!",
            "my_email_password",
            "live_api_key_value_xyz",
            "xkeysib-1234567890abcdef",
            "ghp_PersonalAccessToken12345",
            "long_random_scheduler_hmac_secret",
            "hunter2",
        ]:
            self.assertNotIn(leak, dumped)

    # -------------------------------------------------------------------------
    # 2. HTTP Endpoint Secret Redaction & Parity: /api/config vs /admin/api/config
    # -------------------------------------------------------------------------

    def test_unauthenticated_api_config_rejected(self):
        """Verify unauthenticated requests to /api/config return HTTP 401."""
        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertEqual(data.get("status"), "failed")

    def test_unauthenticated_admin_api_config_rejected(self):
        """Verify unauthenticated requests to /admin/api/config return HTTP 401."""
        res = self.client.get("/admin/api/config")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertEqual(data.get("status"), "failed")

    def test_non_admin_user_api_config_forbidden(self):
        """Verify standard user session receives HTTP 403 on /api/config."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 42
            sess["username"] = "standard_user"
            sess["role"] = "Viewer"

        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertEqual(data.get("status"), "failed")

    def test_non_admin_user_admin_api_config_forbidden(self):
        """Verify standard user session receives HTTP 403 on /admin/api/config."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 42
            sess["username"] = "standard_user"
            sess["role"] = "Viewer"

        res = self.client.get("/admin/api/config")
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertEqual(data.get("status"), "failed")

    def test_authenticated_admin_api_config_sanitized(self):
        """Verify authenticated admin receives sanitized config on /api/config."""
        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"

        res = admin_client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, dict)

        # Verify Deprecation header
        self.assertEqual(res.headers.get("Deprecation"), "true")

        # Verify no raw secrets appear in serialized response
        dumped = str(data).lower()
        self.assertNotIn("password123", dumped)
        self.assertNotIn("ghp_", dumped)
        self.assertNotIn("xkeysib-", dumped)

        # Database URL must be masked if present
        if "database" in data and isinstance(data["database"], dict) and "url" in data["database"]:
            self.assertEqual(data["database"]["url"], "postgresql://user:******@host:port/dbname")

    def test_config_endpoints_return_identical_sanitized_data(self):
        """Verify /api/config and /admin/api/config return identical sanitized payloads."""
        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"

        res_api = admin_client.get("/api/config")
        res_admin = admin_client.get("/admin/api/config")

        self.assertEqual(res_api.status_code, 200)
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_api.get_json(), res_admin.get_json())

    # -------------------------------------------------------------------------
    # 3. CSRF Protection on Operational State-Changing Endpoints
    # -------------------------------------------------------------------------

    def test_admin_api_email_test_csrf_rejection(self):
        """Verify state-changing POST /admin/api/email/test rejects mismatched CSRF token with 403."""
        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"
            sess["admin_csrf_token"] = "valid_admin_csrf_token_secret_1234"

        # Missing CSRF token on browser AJAX request
        res_missing = admin_client.post(
            "/admin/api/email/test",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(res_missing.status_code, 403)
        self.assertIn("CSRF token validation failed", res_missing.get_json().get("error", ""))

        # Invalid CSRF token in header
        res_invalid = admin_client.post(
            "/admin/api/email/test",
            headers={"X-CSRF-Token": "invalid_token_attempt"},
        )
        self.assertEqual(res_invalid.status_code, 403)

    @patch("dashboard.services.api_service.APIService.send_test_email")
    def test_admin_api_email_test_csrf_acceptance(self, mock_send):
        """Verify state-changing POST /admin/api/email/test accepts valid CSRF token in header or body."""
        mock_send.return_value = {"success": True, "status": "completed", "message": "Email sent."}

        admin_client = self.app.test_client()
        csrf_tok = "valid_admin_csrf_token_secret_1234"
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"
            sess["admin_csrf_token"] = csrf_tok

        # Accept via X-CSRF-Token header
        res_hdr = admin_client.post(
            "/admin/api/email/test",
            headers={"X-CSRF-Token": csrf_tok},
        )
        self.assertEqual(res_hdr.status_code, 200)

        # Accept via JSON body
        res_json = admin_client.post(
            "/admin/api/email/test",
            json={"csrf_token": csrf_tok},
        )
        self.assertEqual(res_json.status_code, 200)

    @patch("dashboard.services.api_service.APIService.trigger_scan")
    def test_admin_api_run_csrf_protection(self, mock_scan):
        """Verify POST /admin/api/run requires valid CSRF when admin_csrf_token is in session."""
        mock_scan.return_value = {"job_id": "test-job-uuid-123", "status": "started", "success": True}

        admin_client = self.app.test_client()
        csrf_tok = "admin_scan_csrf_token_5678"
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"
            sess["admin_csrf_token"] = csrf_tok

        # Bad token rejected
        res_bad = admin_client.post(
            "/admin/api/run",
            json={"dry_run": True, "csrf_token": "wrong"},
        )
        self.assertEqual(res_bad.status_code, 403)

        # Valid token accepted
        with patch("dashboard.routes.admin_api.get_db_manager") as mock_db_mgr:
            mock_db_mgr.return_value.ping.return_value = True
            res_good = admin_client.post(
                "/admin/api/run",
                json={"dry_run": True, "csrf_token": csrf_tok},
            )
            self.assertEqual(res_good.status_code, 202)

    # -------------------------------------------------------------------------
    # 4. Explicit Operational Service Boundaries & Input Validation
    # -------------------------------------------------------------------------

    @patch("dashboard.services.api_service.APIService.restart_scheduler")
    def test_admin_scheduler_restart_service_boundary(self, mock_restart):
        """Verify POST /admin/api/scheduler/restart calls api_service.restart_scheduler."""
        mock_restart.return_value = {"success": True, "status": "restarted", "message": "Restarted."}

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"

        res = admin_client.post("/admin/api/scheduler/restart")
        self.assertEqual(res.status_code, 200)
        mock_restart.assert_called_once()

    @patch("dashboard.services.api_service.APIService.send_daily_report_now")
    def test_admin_report_trigger_service_boundary(self, mock_report):
        """Verify POST /admin/api/report/trigger calls api_service.send_daily_report_now."""
        mock_report.return_value = {"success": True, "status": "completed", "message": "Report sent."}

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"

        res = admin_client.post("/admin/api/report/trigger")
        self.assertEqual(res.status_code, 200)
        mock_report.assert_called_once()

    def test_job_id_validation_on_api_jobs(self):
        """Verify /api/jobs/<job_id> validates UUID format and rejects injection attempts."""
        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"

        # Invalid characters or path traversal attempt
        res_invalid = admin_client.get("/api/jobs/../../invalid!id")
        self.assertIn(res_invalid.status_code, [400, 404])

        res_bad_format = admin_client.get("/api/jobs/short")
        self.assertEqual(res_bad_format.status_code, 400)


if __name__ == "__main__":
    unittest.main()
