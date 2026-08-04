"""
Smoke tests for Application Integration & End-to-End Bootstrap.
"""

import unittest

from src.core.bootstrap import CyberScoutApp
from src.core.health import HealthMonitor
from src.core.version import format_banner, get_version_info
from src.main import main


class TestSmoke(unittest.TestCase):
    def test_version_info_and_banner(self):
        info = get_version_info()
        self.assertEqual(info["app_name"], "CyberScout AI")
        self.assertIn(info["version"], ["1.0.0", "1.1.0", "1.1.1"])

        banner = format_banner()
        self.assertIn("CyberScout AI", banner)

    def test_health_monitor(self):
        monitor = HealthMonitor()
        report = monitor.run_full_health_check()
        self.assertIn("healthy", report)
        self.assertTrue(report["healthy"])

    def test_cli_flags(self):
        # Test --version
        self.assertEqual(main(["--version"]), 0)

        # Test --config-check
        self.assertEqual(main(["--config-check"]), 0)

        # Test --db-check
        self.assertEqual(main(["--db-check"]), 0)

        # Test --health
        self.assertEqual(main(["--health"]), 0)


if __name__ == "__main__":
    unittest.main()
