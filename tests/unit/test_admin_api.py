"""
Unit tests for Admin REST API endpoints (/admin/api/*) enforcing RBAC and JSON responses.
"""

from unittest.mock import patch
import unittest

from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.user_repository import UserRepository


class TestAdminAPIEndpoints(unittest.TestCase):

    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

        repo = UserRepository()
        if not repo.get_by_email("regular@cyberscout.ai"):
            try:
                repo.create_user("regularuser", "regular@cyberscout.ai", "UserPass123!", "User")
            except Exception:
                pass

    def test_unauthenticated_admin_api_email_test(self):
        """Verify unauthenticated user receives 401 JSON for /admin/api/email/test."""
        unauth_client = self.app.test_client()
        res = unauth_client.post("/admin/api/email/test")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertIsNotNone(data)
        self.assertEqual(data.get("status"), "failed")

    def test_non_admin_user_admin_api_email_test(self):
        """Verify non-admin user receives 403 JSON for /admin/api/email/test."""
        non_admin_client = self.app.test_client()
        with non_admin_client.session_transaction() as sess:
            sess["user_id"] = 99
            sess["username"] = "regularuser"
            sess["role"] = "User"

        res = non_admin_client.post("/admin/api/email/test")
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIsNotNone(data)
        self.assertEqual(data.get("status"), "failed")

    @patch("dashboard.services.api_service.APIService.send_test_email")
    def test_authenticated_admin_api_email_test_success(self, mock_send):
        """Verify authenticated admin receives HTTP 200 JSON on test email success."""
        mock_send.return_value = {
            "success": True,
            "status": "completed",
            "message": "Test email sent successfully.",
        }

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"

        res = admin_client.post("/admin/api/email/test")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsNotNone(data)
        self.assertTrue(data.get("success"))

    @patch("dashboard.services.api_service.APIService.send_test_email")
    def test_authenticated_admin_api_email_test_failure(self, mock_send):
        """Verify authenticated admin receives HTTP 400 JSON when provider delivery fails."""
        mock_send.return_value = {
            "success": False,
            "status": "failed",
            "error": "[MAIL_SEND] Brevo API key not configured",
        }

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"

        res = admin_client.post("/admin/api/email/test")
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIsNotNone(data)
        self.assertFalse(data.get("success"))
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
