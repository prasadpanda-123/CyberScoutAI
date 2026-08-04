"""
Unit tests for Flask Web Dashboard REST API endpoints.
"""

import json
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_api_health_endpoint(self):
        """GET /api/health"""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("healthy", data)

    def test_api_stats_endpoint(self):
        """GET /api/stats"""
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("total_opportunities", data)

    def test_api_opportunities_endpoint(self):
        """GET /api/opportunities"""
        res = self.client.get("/api/opportunities")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("opportunities", data)

    def test_api_analytics_endpoint(self):
        """GET /api/analytics"""
        res = self.client.get("/api/analytics")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("growth", data)

    def test_api_collectors_endpoint(self):
        """GET /api/collectors"""
        res = self.client.get("/api/collectors")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIsInstance(data, list)

    def test_api_system_endpoint(self):
        """GET /api/system"""
        res = self.client.get("/api/system")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("app_name", data)

    def test_api_scheduler_pause_resume(self):
        """POST /api/scheduler/pause and POST /api/scheduler/resume"""
        res1 = self.client.post("/api/scheduler/pause")
        self.assertEqual(res1.status_code, 200)
        res2 = self.client.post("/api/scheduler/resume")
        self.assertEqual(res2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
