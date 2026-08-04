"""
Unit tests for Link Validator (Phase 12 Feature 3).
"""

import unittest
from src.intelligence.production.link_validator import LinkValidator


class TestLinkValidator(unittest.TestCase):
    def setUp(self):
        self.validator = LinkValidator(timeout=2.0)

    def test_valid_domain_link(self):
        is_valid, code, msg = self.validator.validate_url("https://example.com/test-opportunity")
        self.assertTrue(is_valid)
        self.assertEqual(code, 200)

    def test_invalid_scheme_link(self):
        is_valid, code, msg = self.validator.validate_url("ftp://example.com/file")
        self.assertFalse(is_valid)
        self.assertEqual(code, 400)

    def test_dead_dns_link(self):
        is_valid, code, msg = self.validator.validate_url("https://thisdomainshouldneverexist999111.org/path")
        self.assertFalse(is_valid)
        self.assertEqual(code, 502)


if __name__ == "__main__":
    unittest.main()
