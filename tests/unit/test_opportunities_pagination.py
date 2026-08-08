"""
Unit tests for Opportunities server-side pagination logic, input sanitization, and security.
"""

import math
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from dashboard.services.dashboard_service import DashboardService


class TestOpportunitiesPagination(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.dash_service = DashboardService()
        self.user_client = self.app.test_client()

        # Set up standard authenticated user session
        with self.user_client.session_transaction() as sess:
            sess["user_id"] = 100
            sess["username"] = "testuser"
            sess["email"] = "testuser@cyberscout.ai"
            sess["role"] = "User"

    def test_pagination_defaults(self):
        """Test default opportunities request returns expected structure."""
        res = self.user_client.get("/opportunities")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Opportunities Explorer", html)
        self.assertIn("Per Page", html)

    def test_pagination_page_1(self):
        """Test explicit page 1 parameter."""
        res = self.user_client.get("/opportunities?page=1&per_page=20")
        self.assertEqual(res.status_code, 200)

    def test_pagination_invalid_page_numbers(self):
        """Test invalid page numbers like 0, negative numbers, or strings do not crash app."""
        for invalid_p in ["0", "-1", "-99", "abc", "null"]:
            res = self.user_client.get(f"/opportunities?page={invalid_p}")
            self.assertEqual(res.status_code, 200)

    def test_pagination_invalid_per_page(self):
        """Test invalid per_page parameters fallback safely to 20."""
        for invalid_pp in ["0", "-20", "999999", "xyz"]:
            res = self.user_client.get(f"/opportunities?per_page={invalid_pp}")
            self.assertEqual(res.status_code, 200)

    def test_pagination_out_of_bounds_page(self):
        """Test requesting a page beyond total_pages returns safely without error."""
        res = self.user_client.get("/opportunities?page=999999&per_page=20")
        self.assertEqual(res.status_code, 200)

    def test_search_and_category_filter_preserves_in_pagination(self):
        """Test search query and category filters are preserved in response HTML."""
        res = self.user_client.get("/opportunities?q=cyber&category=ctf&page=1&per_page=50")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn('value="cyber"', html)
        self.assertIn('value="ctf" selected', html)

    def test_service_layer_pagination(self):
        """Test DashboardService get_opportunities return_total parameter structure."""
        data = self.dash_service.get_opportunities(limit=20, offset=0, return_total=True)
        self.assertIsInstance(data, dict)
        self.assertIn("items", data)
        self.assertIn("total_count", data)
        self.assertIsInstance(data["items"], list)
        self.assertIsInstance(data["total_count"], int)
        self.assertTrue(len(data["items"]) <= 20)

    def test_unauthenticated_opportunities_access_redirects_to_landing(self):
        """Test unauthenticated direct request to /opportunities redirects to landing page '/'."""
        unauth_client = self.app.test_client()
        res = unauth_client.get("/opportunities")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/"))


if __name__ == "__main__":
    unittest.main()
