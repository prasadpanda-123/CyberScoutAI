"""
Unit tests for Global Configuration & Source Validation Framework.
"""

import unittest
from unittest.mock import patch

from src.core.config_validator import ConfigurationValidator
from src.core.provider_health import ProviderHealthChecker
from src.utils.url_utils import is_valid_url, sanitize_url


class TestConfigValidationFramework(unittest.TestCase):
    """Tests URL sanitization, ConfigurationValidator, and ProviderHealthChecker."""

    def test_sanitize_url_valid_http_https(self):
        """Verify valid URLs are normalized."""
        self.assertEqual(sanitize_url("https://api.github.com/search//repositories"), "https://api.github.com/search/repositories")
        self.assertEqual(sanitize_url("http://feeds.feedburner.com/TheHackersNews/"), "http://feeds.feedburner.com/TheHackersNews/")

    def test_sanitize_url_hostname_underscore_fixing(self):
        """Verify invalid hostname underscores (e.g. portswigger_academy.com) are converted or mapped."""
        fixed = sanitize_url("https://portswigger_academy.com/web-security")
        self.assertEqual(fixed, "https://portswigger.net/web-security")
        self.assertNotIn("portswigger_academy.com", fixed)

    def test_sanitize_url_rejects_dangerous_schemes(self):
        """Verify forbidden protocol schemes are rejected."""
        with self.assertRaises(ValueError):
            sanitize_url("file:///etc/passwd")
        with self.assertRaises(ValueError):
            sanitize_url("javascript:alert(1)")
        with self.assertRaises(ValueError):
            sanitize_url("http://localhost:8080/api")

    def test_is_valid_url_helper(self):
        """Verify is_valid_url helper function."""
        self.assertTrue(is_valid_url("https://ctftime.org/api/v1/events/"))
        self.assertFalse(is_valid_url("file:///tmp/secret"))
        self.assertFalse(is_valid_url("http://127.0.0.1/admin"))

    def test_configuration_validator(self):
        """Verify ConfigurationValidator audits config directory."""
        validator = ConfigurationValidator()
        report = validator.validate_all()
        self.assertGreater(report.total_files, 0)
        self.assertGreater(report.total_sources, 0)
        self.assertTrue(report.is_valid)

    def test_provider_health_checker(self):
        """Verify ProviderHealthChecker evaluates sources."""
        checker = ProviderHealthChecker()
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
            results = checker.check_all_providers(timeout_seconds=0.1)
            self.assertGreater(len(results), 0)
            enabled_results = [r for r in results if r.status != "Disabled"]
            for r in enabled_results:
                self.assertIn(r.status, ["Healthy", "Warning", "Broken"])


if __name__ == "__main__":
    unittest.main()
