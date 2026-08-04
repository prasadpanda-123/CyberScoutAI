"""
Unit tests for Content Verifier (Phase 12 Feature 4).
"""

import unittest
from src.intelligence.production.content_verifier import ContentVerifier


class TestContentVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = ContentVerifier()

    def test_valid_opportunity_content(self):
        is_ver, msg = self.verifier.verify_content(
            title="OWASP Vulnerability Analyst Internship",
            description="Learn web security, pentesting, and secure coding practices.",
        )
        self.assertTrue(is_ver)
        self.assertEqual(msg, "VERIFIED")

    def test_login_gate_rejection(self):
        is_ver, msg = self.verifier.verify_content(
            title="Private Opportunity",
            description="Please log in to continue accessing this portal.",
        )
        self.assertFalse(is_ver)
        self.assertEqual(msg, "LOGIN_GATE_DETECTED")

    def test_parked_domain_rejection(self):
        is_ver, msg = self.verifier.verify_content(
            title="Cyber Security Hub",
            description="This domain is parked. Buy this domain now.",
        )
        self.assertFalse(is_ver)
        self.assertEqual(msg, "PARKED_DOMAIN")


if __name__ == "__main__":
    unittest.main()
