"""
Phase 4 Unit Tests: Content Security Policy (CSP) & Browser Security Hardening.

Verifies:
1. CSP Header Presence and Directive Correctness.
2. Nonce Generation: Cryptographically random, response-scoped, and isolated across requests.
3. Nonce Reflection: Rendered HTML script tags contain matching nonces.
4. Absence of 'unsafe-eval' from script-src.
5. Absence of unused external origins (e.g. cdn.jsdelivr.net).
6. Presence of Hardened Directives: object-src 'none', base-uri 'self', form-action 'self', frame-ancestors 'none'.
7. Preservation of OWASP Top 10 Security Headers.
"""

import re
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestPhase4CspSecurity(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_csp_header_presence_and_structure(self):
        """Verify Content-Security-Policy header exists and contains required directives."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        csp = res.headers.get("Content-Security-Policy")
        self.assertIsNotNone(csp, "Content-Security-Policy header must be present")

        # Required base directives
        self.assertIn("default-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("base-uri 'self'", csp)
        self.assertIn("form-action 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("img-src 'self' data: https:", csp)

    def test_elimination_of_unsafe_eval(self):
        """Verify 'unsafe-eval' is completely eliminated from script-src."""
        for path in ["/", "/login", "/admin/login"]:
            res = self.client.get(path)
            csp = res.headers.get("Content-Security-Policy", "")
            self.assertNotIn("'unsafe-eval'", csp, f"'unsafe-eval' must not appear in CSP for {path}")

    def test_elimination_of_unused_cdn_origins(self):
        """Verify unused CDN domains (jsdelivr) are removed from all directives."""
        res = self.client.get("/")
        csp = res.headers.get("Content-Security-Policy", "")
        self.assertNotIn("cdn.jsdelivr.net", csp, "cdn.jsdelivr.net must be removed from CSP")

    def test_elimination_of_cdn_tailwindcss(self):
        """Verify cdn.tailwindcss.com is completely removed from CSP."""
        res = self.client.get("/")
        csp = res.headers.get("Content-Security-Policy", "")
        self.assertNotIn("cdn.tailwindcss.com", csp, "cdn.tailwindcss.com must not appear in CSP")

    def test_elimination_of_unsafe_inline(self):
        """Verify 'unsafe-inline' is eliminated from script-src and style-src."""
        res = self.client.get("/")
        csp = res.headers.get("Content-Security-Policy", "")
        # Parse directives
        directives = {d.split()[0]: d for d in csp.split(";") if d.strip()}
        script_src = directives.get("script-src", "")
        style_src = directives.get("style-src", "")
        self.assertNotIn("'unsafe-inline'", script_src, "'unsafe-inline' must not be in script-src")
        self.assertNotIn("'unsafe-inline'", style_src, "'unsafe-inline' must not be in style-src")

    def test_permitted_legitimate_origins(self):
        """Verify necessary external styling and font assets are explicitly permitted."""
        res = self.client.get("/")
        csp = res.headers.get("Content-Security-Policy", "")
        self.assertIn("https://fonts.googleapis.com", csp)
        self.assertIn("https://fonts.gstatic.com", csp)

    def test_nonce_generation_and_uniqueness(self):
        """Verify cryptographic nonce is generated per-response and unique across requests."""
        nonces = set()
        for i in range(10):
            res = self.client.get("/")
            csp = res.headers.get("Content-Security-Policy", "")
            match = re.search(r"'nonce-([^']+)'", csp)
            self.assertIsNotNone(match, f"Nonce missing from CSP header on iteration {i}")
            nonce = match.group(1)
            self.assertGreaterEqual(len(nonce), 16, "Nonce must be at least 16 bytes/characters")
            self.assertNotIn(nonce, nonces, f"Duplicate nonce detected on iteration {i}: {nonce}")
            nonces.add(nonce)

    def test_nonce_isolation_between_requests(self):
        """Verify Request A nonce != Request B nonce and is response-scoped."""
        res_a = self.client.get("/login")
        csp_a = res_a.headers.get("Content-Security-Policy", "")
        nonce_a = re.search(r"'nonce-([^']+)'", csp_a).group(1)

        res_b = self.client.get("/login")
        csp_b = res_b.headers.get("Content-Security-Policy", "")
        nonce_b = re.search(r"'nonce-([^']+)'", csp_b).group(1)

        self.assertNotEqual(nonce_a, nonce_b, "Nonces must be strictly isolated between requests")

    def test_rendered_script_tags_contain_matching_nonce(self):
        """Verify all rendered <script> tags contain the matching response CSP nonce."""
        test_routes = ["/login", "/admin/login"]
        for route in test_routes:
            res = self.client.get(route)
            csp = res.headers.get("Content-Security-Policy", "")
            header_nonce = re.search(r"'nonce-([^']+)'", csp).group(1)

            html = res.get_data(as_text=True)
            all_scripts = re.findall(r'<script[^>]*>', html)
            self.assertGreater(len(all_scripts), 0, f"Expected scripts in {route}")

            # Verify every script has nonce matching header_nonce
            for script_tag in all_scripts:
                self.assertIn(
                    f'nonce="{header_nonce}"',
                    script_tag,
                    f"Script tag in {route} does not have matching nonce: {script_tag}"
                )

    def test_security_headers_regression_preservation(self):
        """Verify all other standard security headers remain active and unchanged."""
        res = self.client.get("/")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(res.headers.get("Permissions-Policy"), "geolocation=(), camera=(), microphone=()")
        self.assertIn("max-age=31536000", res.headers.get("Strict-Transport-Security", ""))
        self.assertIsNone(res.headers.get("Server"))
        self.assertIsNone(res.headers.get("X-Powered-By"))


if __name__ == "__main__":
    unittest.main()
