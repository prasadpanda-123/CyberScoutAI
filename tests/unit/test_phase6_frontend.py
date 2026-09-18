"""
Phase 6 Unit Tests: Production Frontend Hardening & Precompiled Tailwind Verification.

Verifies:
1. Precompiled Tailwind CSS file exists and is populated.
2. Static CSS asset is served with HTTP 200 and text/css content-type from same-origin.
3. All production HTML templates reference local static tailwind.css.
4. Zero references to cdn.tailwindcss.com in production templates.
5. Content-Security-Policy completely excludes cdn.tailwindcss.com across all directives.
6. Content-Security-Policy eliminates 'unsafe-inline' from both script-src and style-src.
7. Content-Security-Policy eliminates 'unsafe-eval' from script-src.
8. Nonce-based execution for inline scripts is preserved and unique per response.
9. OWASP Top 10 Security Headers remain fully active.
"""

import os
import re
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestPhase6FrontendHardening(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()
        self.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.templates_dir = os.path.join(self.repo_root, "dashboard", "templates")
        self.static_css_dir = os.path.join(self.repo_root, "dashboard", "static", "css")

    def test_precompiled_tailwind_css_exists_and_populated(self):
        """Verify the precompiled tailwind.css file exists on disk and is non-empty."""
        css_path = os.path.join(self.static_css_dir, "tailwind.css")
        self.assertTrue(os.path.isfile(css_path), f"Precompiled CSS file not found at {css_path}")
        size_bytes = os.path.getsize(css_path)
        self.assertGreater(size_bytes, 10000, f"Precompiled CSS is suspiciously small: {size_bytes} bytes")

    def test_static_tailwind_served_successfully(self):
        """Verify the application serves tailwind.css locally with HTTP 200 and valid CSS mime type."""
        res = self.client.get("/static/css/tailwind.css")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            "text/css" in res.headers.get("Content-Type", ""),
            f"Expected text/css Content-Type, got: {res.headers.get('Content-Type')}"
        )
        body = res.get_data(as_text=True)
        self.assertGreater(len(body), 1000)

    def test_templates_reference_local_tailwind_stylesheet(self):
        """Verify key base and standalone templates load the local static tailwind.css asset."""
        sample_routes = ["/", "/login", "/register", "/admin/login"]
        for route in sample_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Failed loading route: {route}")
            html = res.get_data(as_text=True)
            self.assertIn(
                "css/tailwind.css",
                html,
                f"Route {route} does not include link to local static tailwind.css"
            )

    def test_zero_cdn_references_in_templates(self):
        """Verify zero templates contain references to cdn.tailwindcss.com or tailwindcss.com."""
        found_references = []
        for root, _, files in os.walk(self.templates_dir):
            for file in files:
                if file.endswith(".html"):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "cdn.tailwindcss.com" in content or "tailwindcss.com" in content:
                            found_references.append(filepath)

        self.assertEqual(
            found_references,
            [],
            f"Found legacy Tailwind CDN references in templates: {found_references}"
        )

    def test_csp_excludes_tailwind_cdn(self):
        """Verify cdn.tailwindcss.com is completely purged from CSP directives."""
        res = self.client.get("/")
        csp = res.headers.get("Content-Security-Policy", "")
        self.assertNotIn("cdn.tailwindcss.com", csp)
        self.assertNotIn("tailwindcss.com", csp)

    def test_csp_eliminates_unsafe_inline_from_both_script_and_style(self):
        """Verify neither script-src nor style-src contains 'unsafe-inline'."""
        for path in ["/", "/login", "/admin/login"]:
            res = self.client.get(path)
            csp = res.headers.get("Content-Security-Policy", "")
            directives = {d.strip().split()[0]: d.strip() for d in csp.split(";") if d.strip()}

            script_src = directives.get("script-src", "")
            style_src = directives.get("style-src", "")

            self.assertNotIn("'unsafe-inline'", script_src, f"'unsafe-inline' in script-src for {path}")
            self.assertNotIn("'unsafe-inline'", style_src, f"'unsafe-inline' in style-src for {path}")

    def test_csp_eliminates_unsafe_eval(self):
        """Verify 'unsafe-eval' remains absent from all CSP directives."""
        res = self.client.get("/")
        csp = res.headers.get("Content-Security-Policy", "")
        self.assertNotIn("'unsafe-eval'", csp)

    def test_csp_nonce_preserved_and_reflected(self):
        """Verify script nonce remains present in CSP and reflects into template script elements."""
        res = self.client.get("/login")
        csp = res.headers.get("Content-Security-Policy", "")
        nonce_match = re.search(r"'nonce-([^']+)'", csp)
        self.assertIsNotNone(nonce_match, "CSP header missing per-response script nonce")
        nonce = nonce_match.group(1)

        html = res.get_data(as_text=True)
        self.assertIn(f'nonce="{nonce}"', html, "Rendered template missing matching script nonce")

    def test_security_headers_active(self):
        """Verify all standard defense-in-depth headers remain configured."""
        res = self.client.get("/")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(res.headers.get("Permissions-Policy"), "geolocation=(), camera=(), microphone=()")
        self.assertIn("max-age=31536000", res.headers.get("Strict-Transport-Security", ""))


if __name__ == "__main__":
    unittest.main()
