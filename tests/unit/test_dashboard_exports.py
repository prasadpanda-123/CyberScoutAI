"""
Unit tests for Dashboard standard user export removal and authorization security.
"""

import json
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestDashboardExports(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.user_client = self.app.test_client()
        self.admin_client = self.app.test_client()
        self.unauth_client = self.app.test_client()

        # Set up standard user session
        with self.user_client.session_transaction() as sess:
            sess["user_id"] = 999
            sess["username"] = "testuser"
            sess["email"] = "testuser@cyberscout.ai"
            sess["role"] = "User"

        # Set up admin user session
        with self.admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "adminuser"
            sess["admin_role"] = "Super Admin"
            sess["admin_csrf_token"] = "test_admin_csrf_token"
            sess["user_id"] = 1
            sess["username"] = "adminuser"
            sess["role"] = "Super Admin"

    def test_unauthenticated_user_cannot_access_export_endpoint(self):
        """TEST 1: Unauthenticated user cannot access export endpoints."""
        res_csv = self.unauth_client.get("/opportunities/export/csv")
        self.assertIn(res_csv.status_code, [302, 404])

        res_json = self.unauth_client.get("/opportunities/export/json")
        self.assertIn(res_json.status_code, [302, 404])

        res_admin_export = self.unauth_client.get("/admin/api/logs/export")
        self.assertIn(res_admin_export.status_code, [401, 403])

    def test_authenticated_standard_user_cannot_access_export_endpoint(self):
        """TEST 2: Authenticated standard user cannot access user export endpoints or admin export endpoints."""
        res_csv = self.user_client.get("/opportunities/export/csv")
        self.assertIn(res_csv.status_code, [302, 404])

        res_json = self.user_client.get("/opportunities/export/json")
        self.assertIn(res_json.status_code, [302, 404])

        # Direct access attempt to admin log export route returns HTTP 403
        res_admin_export = self.user_client.get("/admin/api/logs/export")
        self.assertEqual(res_admin_export.status_code, 403)

    def test_administrator_can_access_admin_export_endpoint(self):
        """TEST 3: Authenticated administrator can access admin-only export endpoint."""
        res = self.admin_client.get("/admin/api/logs/export")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/json")

    def test_opportunities_page_does_not_render_export_csv(self):
        """TEST 4: Opportunities page does not render Export CSV."""
        res = self.user_client.get("/opportunities")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertNotIn("Export CSV", html)
        self.assertNotIn("/opportunities/export/csv", html)

    def test_opportunities_page_does_not_render_export_json(self):
        """TEST 5: Opportunities page does not render Export JSON."""
        res = self.user_client.get("/opportunities")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertNotIn("Export JSON", html)
        self.assertNotIn("/opportunities/export/json", html)

    def test_no_user_side_javascript_calls_export_endpoints(self):
        """TEST 6: No user-side JavaScript attempts to call export endpoints."""
        res = self.user_client.get("/opportunities")
        html = res.data.decode("utf-8")
        self.assertNotIn("exportCSV", html)
        self.assertNotIn("exportJSON", html)
        self.assertNotIn("exportOpportunities", html)

    def test_normal_opportunity_browsing_works(self):
        """TEST 7: Normal opportunity browsing still works."""
        res = self.user_client.get("/opportunities")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertTrue("Opportunities Hub" in html or "Opportunities" in html)
        self.assertIn("Category", html)


    def test_search_and_filtering_still_work(self):
        """TEST 8: Search and filtering still work."""
        res = self.user_client.get("/opportunities?q=cyber&category=internship")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Search & Filter", html)
        self.assertIn("cyber", html)

    def test_opening_opportunity_still_works(self):
        """TEST 9: Opening an opportunity link still works."""
        res = self.user_client.get("/opportunities")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Open", html)


if __name__ == "__main__":
    unittest.main()

