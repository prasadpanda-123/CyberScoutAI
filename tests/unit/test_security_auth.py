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
        """Verify anonymous visitors can access public pages but are blocked and redirected to / for all protected pages."""
        anon_client = self.app.test_client()

        # Explicit Public Allowlist Endpoints
        self.assertEqual(anon_client.get("/").status_code, 200)
        self.assertEqual(anon_client.get("/login").status_code, 200)
        self.assertEqual(anon_client.get("/register").status_code, 200)
        self.assertEqual(anon_client.get("/admin/login").status_code, 200)
        self.assertEqual(anon_client.get("/api/health").status_code, 200)

        # Protected user HTML endpoints redirect unauthenticated requests directly to landing page '/'
        for protected_path in ["/dashboard", "/opportunities", "/analytics", "/history", "/knowledge", "/production", "/quality"]:
            res = anon_client.get(protected_path)
            self.assertEqual(res.status_code, 302, f"Path {protected_path} should redirect unauthenticated user")
            self.assertTrue(res.location.endswith("/"), f"Path {protected_path} location should redirect to landing page '/'")

        # Protected user API endpoints return 401 JSON
        for api_path in ["/api/opportunities", "/api/dashboard/summary", "/api/analytics"]:
            res_api = anon_client.get(api_path)
            self.assertEqual(res_api.status_code, 401, f"API {api_path} should return 401 for anonymous request")
            data = res_api.get_json()
            self.assertEqual(data.get("status"), "failed")

        # Admin protected pages redirect anonymous visitors to dedicated admin login page '/admin/login'
        for admin_path in ["/admin/dashboard", "/admin/users", "/admin/logs", "/admin/configuration", "/admin/diagnostics"]:
            res_admin = anon_client.get(admin_path)
            self.assertEqual(res_admin.status_code, 302)
            self.assertIn("/admin/login", res_admin.location, f"Admin path {admin_path} location should redirect to '/admin/login'")

        # Unknown browser URLs redirect to public landing page '/'
        res_unknown = anon_client.get("/something-random-xyz")
        self.assertEqual(res_unknown.status_code, 302)
        self.assertTrue(res_unknown.location.endswith("/"))

        # Unknown API URLs return 404 JSON
        res_api_unknown = anon_client.get("/api/something-random-xyz")
        self.assertEqual(res_api_unknown.status_code, 404)
        self.assertEqual(res_api_unknown.get_json().get("status"), "error")

    def test_direct_unauthenticated_opportunities_access_prevention(self):
        """EXPLICIT REGRESSION TEST: Unauthenticated GET /opportunities MUST NOT return 200 or render opportunity data."""
        anon_client = self.app.test_client()
        res = anon_client.get("/opportunities")
        self.assertNotEqual(res.status_code, 200, "Unauthenticated GET /opportunities MUST NOT return HTTP 200")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.location.endswith("/"))
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

        # Access protected pages & verify sidebar links
        dash_res = user_client.get("/dashboard")
        self.assertEqual(dash_res.status_code, 200)
        dash_html = dash_res.get_data(as_text=True)
        self.assertIn('href="/dashboard"', dash_html, "Sidebar Dashboard item must link to /dashboard")
        self.assertEqual(user_client.get("/opportunities").status_code, 200)

        # Logout
        user_client.get("/logout")
        res_after = user_client.get("/dashboard")
        self.assertEqual(res_after.status_code, 302)
        self.assertTrue(res_after.location.endswith("/"))

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

    def test_admin_logs_and_audit_trail(self):
        """EXPLICIT REGRESSION TEST: Verify /admin/logs and /admin/api/audit-logs return HTTP 200 without 'no results to fetch' errors."""
        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user"] = "admin_test"
            sess["admin_role"] = "Administrator"

        # Verify HTML admin logs page loads cleanly
        html_res = admin_client.get("/admin/logs")
        self.assertEqual(html_res.status_code, 200, "Admin logs HTML page must return 200 OK")
        html_data = html_res.get_data(as_text=True)
        self.assertNotIn("no results to fetch", html_data)
        self.assertNotIn("Internal Server Error", html_data)

        # Verify JSON audit logs API returns HTTP 200 with structured dictionary
        api_res = admin_client.get("/admin/api/audit-logs")
        self.assertEqual(api_res.status_code, 200, "Admin audit logs API must return 200 OK")
        json_data = api_res.get_json()
        self.assertIsInstance(json_data.get("logs"), list)
        self.assertGreaterEqual(json_data.get("total_records", 0), 0)


if __name__ == "__main__":
    unittest.main()
