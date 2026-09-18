"""
Unit tests for Landing Page Sign In and Authentication Route Isolation.
Verifies that:
1. Landing page Sign In link resolves to standard user login URL (/login).
2. Landing page does not contain an admin login link for the public Sign In action.
3. Standard user login page loads successfully (HTTP 200).
4. Admin login page remains available at its dedicated route (/admin/login).
5. Standard-user protected route redirects to standard user login (/login).
6. Admin-protected route redirects to admin login (/admin/login).
7. Invalid or external next URLs are rejected safely.
8. Existing admin MFA flow remains functional.
9. Existing CSRF and session protections remain functional.
10. Standard and admin identities remain strictly separated.
"""

import unittest
from bs4 import BeautifulSoup
from dashboard.app import create_app
from src.auth.admin_auth import AdminSecurityManager
from src.database.connection import DatabaseManager
from src.database.admin_repository import AdminRepository
from src.database.user_repository import UserRepository


class TestAuthLandingRedirect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.db = DatabaseManager()
        cls.admin_repo = AdminRepository(cls.db)
        cls.user_repo = UserRepository(cls.db)

    def setUp(self):
        # Fresh isolated client for each test method to prevent session leakage
        self.client = self.app.test_client()

    def test_1_landing_signin_link_resolves_to_user_login(self):
        """Landing page Sign In link must resolve to standard user login (/login)."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        soup = BeautifulSoup(res.data.decode("utf-8"), "html.parser")
        
        # Find all links with text "Sign In"
        signin_links = [a for a in soup.find_all("a") if a.get_text(strip=True) == "Sign In"]
        self.assertGreaterEqual(len(signin_links), 1)
        for link in signin_links:
            self.assertEqual(link.get("href"), "/login")

    def test_2_landing_does_not_contain_admin_link_for_public_signin(self):
        """Public Sign In and CTA actions must not point to /admin/login."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        soup = BeautifulSoup(res.data.decode("utf-8"), "html.parser")

        # Check navigation and hero CTA buttons
        nav_links = soup.find("nav").find_all("a") if soup.find("nav") else []
        for link in nav_links:
            text = link.get_text(strip=True)
            if "Sign In" in text or "Get Started" in text:
                self.assertNotIn("/admin", link.get("href", ""))

        hero_links = soup.find("header").find_all("a") if soup.find("header") else []
        for link in hero_links:
            text = link.get_text(strip=True)
            if "Explore" in text or "Access Portal" in text:
                self.assertNotIn("/admin", link.get("href", ""))

    def test_3_standard_user_login_page_loads(self):
        """Standard user login page (/login) loads with HTTP 200 and standard form."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Sign in to your account", html)
        self.assertIn('action="/login"', html)
        self.assertNotIn('action="/admin/login"', html)

    def test_4_admin_login_page_dedicated_route(self):
        """Admin login page loads at /admin/login and contains dedicated admin form."""
        res = self.client.get("/admin/login")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Admin Gateway", html)
        self.assertIn('action="/admin/login"', html)

    def test_5_standard_protected_route_redirects_to_user_login(self):
        """Unauthenticated access to user-protected route redirects to /login?next=..."""
        res = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("Location", "")
        self.assertTrue(location.startswith("/login"))
        self.assertNotIn("/admin/login", location)

    def test_6_admin_protected_route_redirects_to_admin_login(self):
        """Unauthenticated access to admin-protected route redirects to /admin/login."""
        # Test /admin
        res = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("Location", "")
        self.assertTrue(location.startswith("/admin/login"))

        # Test /admin/dashboard
        res_dash = self.client.get("/admin/dashboard", follow_redirects=False)
        self.assertEqual(res_dash.status_code, 302)
        location_dash = res_dash.headers.get("Location", "")
        self.assertTrue(location_dash.startswith("/admin/login"))

    def test_7_invalid_or_external_next_urls_rejected(self):
        """External or malformed next URLs in /login redirect to safe fallback."""
        res = self.client.get("/login?next=https://evil.example.com")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        # Ensure unsafe next is not emitted as input value
        self.assertNotIn('value="https://evil.example.com"', html)

    def test_8_admin_mfa_flow_remains_functional(self):
        """Admin MFA state generation and code verification remain functional."""
        otp_code = AdminSecurityManager.generate_otp_code()
        self.assertEqual(len(otp_code), 6)
        self.assertTrue(otp_code.isdigit())
        hashed = AdminSecurityManager.hash_otp_code(otp_code)
        self.assertTrue(AdminSecurityManager.verify_otp_code(otp_code, hashed))

    def test_9_csrf_and_session_protections_functional(self):
        """CSRF token generation and validation operate correctly."""
        token = AdminSecurityManager.generate_csrf_token()
        self.assertTrue(isinstance(token, str))
        self.assertGreater(len(token), 32)
        self.assertTrue(AdminSecurityManager.verify_csrf_token(token, token))
        self.assertFalse(AdminSecurityManager.verify_csrf_token(token, "tampered_token"))

    def test_10_identities_remain_strictly_separated(self):
        """Admin and user roles remain separated; standard user cannot access /admin/dashboard."""
        # Authenticate as standard viewer
        with self.client.session_transaction() as sess:
            sess["user_id"] = "00000000-0000-0000-0000-000000000001"
            sess["username"] = "standard_viewer"
            sess["role"] = "Viewer"

        # Attempt to access admin dashboard
        admin_res = self.client.get("/admin/dashboard", follow_redirects=False)
        self.assertEqual(admin_res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
