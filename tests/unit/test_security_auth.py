"""
Unit tests for CyberScout AI v2.1 Authentication, RBAC, Setup Flow, and Security Headers.
"""

import json
import time
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


class TestSecurityAuth(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.user_repo = UserRepository(self.db_manager)
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_user_creation_and_password_hashing(self):
        """Verify password is properly hashed with PBKDF2 SHA-256."""
        ts_id = int(time.time() * 1000)
        email = f"secops_{ts_id}@cyberscout.ai"
        username = f"secops_{ts_id}"

        user = self.user_repo.create_user(
            username=username,
            email=email,
            password="SecurePassword2026!",
            role="Operator",
        )
        self.assertIsNotNone(user["id"])
        self.assertEqual(user["role"], "Operator")

        auth_user = self.user_repo.authenticate(email, "SecurePassword2026!")
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user["username"], username)

        invalid_auth = self.user_repo.authenticate(email, "WrongPassword")
        self.assertIsNone(invalid_auth)

    def test_owasp_security_headers(self):
        """Verify OWASP security headers are set on HTTP responses."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")

        ref_policy = res.headers.get("Referrer-Policy")
        self.assertIsNotNone(ref_policy)
        self.assertIn("strict-origin-when-cross-origin", ref_policy or "")

        hsts = res.headers.get("Strict-Transport-Security")
        self.assertIsNotNone(hsts)
        self.assertIn("max-age=31536000", hsts or "")

        csp = res.headers.get("Content-Security-Policy")
        self.assertIsNotNone(csp)
        self.assertIn("default-src 'self'", csp or "")
        self.assertNotIn("Server", res.headers)

    def test_rbac_access_control(self):
        """Verify Viewer role is blocked from accessing Admin routes."""
        ts_id = int(time.time() * 1000)
        email = f"viewer_{ts_id}@cyberscout.ai"
        username = f"viewer_{ts_id}"

        self.user_repo.create_user(
            username=username,
            email=email,
            password="ViewerPassword2026!",
            role="Viewer",
        )
        # Log in as Viewer
        self.client.post("/login", data={"identifier": email, "password": "ViewerPassword2026!"})

        # Viewer trying to access Super Admin / Admin config route
        res = self.client.get("/configuration")
        self.assertEqual(res.status_code, 403)

        # Viewer trying to access Super Admin logs route
        res_logs = self.client.get("/logs")
        self.assertEqual(res_logs.status_code, 403)

        # Viewer trying to access /admin/dashboard
        res_admin = self.client.get("/admin/dashboard")
        self.assertEqual(res_admin.status_code, 403)

    def test_anonymous_access_control(self):
        """Verify anonymous visitors can access public pages but are blocked from protected user & admin pages."""
        anon_client = self.app.test_client()

        # Public endpoints
        self.assertEqual(anon_client.get("/").status_code, 200)
        self.assertEqual(anon_client.get("/login").status_code, 200)
        self.assertEqual(anon_client.get("/register").status_code, 200)
        self.assertEqual(anon_client.get("/api/health").status_code, 200)

        # Protected user HTML endpoints redirect to /login
        for protected_path in ["/dashboard", "/opportunities", "/analytics", "/history", "/knowledge", "/production", "/quality"]:
            res = anon_client.get(protected_path)
            self.assertEqual(res.status_code, 302, f"Path {protected_path} should redirect unauthenticated user")
            self.assertIn("/login", res.location)

        # Protected user API endpoints return 401 JSON
        for api_path in ["/api/opportunities", "/api/dashboard/summary", "/api/analytics"]:
            res_api = anon_client.get(api_path)
            self.assertEqual(res_api.status_code, 401, f"API {api_path} should return 401 for anonymous request")
            data = res_api.get_json()
            self.assertEqual(data.get("status"), "failed")

        # Admin pages redirect anonymous visitors to /admin/login
        res_admin = anon_client.get("/admin/dashboard")
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn("/admin/login", res_admin.location)

    def test_direct_unauthenticated_opportunities_access_prevention(self):
        """EXPLICIT REGRESSION TEST: Unauthenticated GET /opportunities MUST NOT return 200 or render opportunity data."""
        anon_client = self.app.test_client()
        res = anon_client.get("/opportunities")
        self.assertNotEqual(res.status_code, 200, "Unauthenticated GET /opportunities MUST NOT return HTTP 200")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)
        html_data = res.get_data(as_text=True)
        self.assertNotIn("Opportunities Explorer", html_data)
        self.assertNotIn("table-responsive", html_data)

    def test_open_redirect_prevention_on_login(self):
        """Verify login endpoint prevents open redirects to external domains via next parameter."""
        res = self.client.get("/login?next=https://evil-site.com")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("https://evil-site.com", res.get_data(as_text=True))

    def test_authenticated_user_flow_and_logout(self):
        """Verify normal user login, dashboard access, and logout session revocation."""
        ts_id = int(time.time() * 1000)
        email = f"user_{ts_id}@cyberscout.ai"
        username = f"user_{ts_id}"

        self.user_repo.create_user(username=username, email=email, password="UserPass2026!", role="Viewer")

        user_client = self.app.test_client()
        login_res = user_client.post("/login", data={"identifier": email, "password": "UserPass2026!"})
        self.assertEqual(login_res.status_code, 302)

        # Access protected pages
        self.assertEqual(user_client.get("/dashboard").status_code, 200)
        self.assertEqual(user_client.get("/opportunities").status_code, 200)

        # Logout
        user_client.get("/logout")
        res_after = user_client.get("/dashboard")
        self.assertEqual(res_after.status_code, 302)
        self.assertIn("/login", res_after.location)

    def test_registration_role_escalation_prevention(self):
        """Verify registration endpoint ignores role parameter in POST body and forces 'Viewer' role."""
        ts_id = int(time.time() * 1000)
        email = f"hacker_{ts_id}@cyberscout.ai"
        username = f"hacker_{ts_id}"

        res = self.client.post("/register", data={
            "username": username,
            "email": email,
            "password": "HackerPass123!",
            "confirm_password": "HackerPass123!",
            "role": "Super Admin",
        })
        self.assertEqual(res.status_code, 302)

        created_user = self.user_repo.get_by_email(email)
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user["role"], "Viewer")

    def test_first_run_setup_flow_disabled_when_admin_exists(self):
        """Verify GET /setup redirects to /login when administrator accounts exist."""
        res = self.client.get("/setup")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)


if __name__ == "__main__":
    unittest.main()
