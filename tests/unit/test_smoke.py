"""
Smoke tests for Application Integration & End-to-End Bootstrap (Phase 1.5).
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
        self.assertEqual(info["version"], "0.1.0")

        banner = format_banner()
        self.assertIn("CyberScout AI v0.1.0", banner)

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

    def test_app_startup_and_shutdown_smoke(self):
        app = CyberScoutApp()
        context = app.startup()
        self.assertIsNotNone(context)
        self.assertIsNotNone(context.config)
        self.assertIsNotNone(context.db_manager)
        self.assertIsNotNone(context.repositories)
        self.assertIsNotNone(context.scheduler)
        self.assertTrue(app.is_initialized)

        app.shutdown()
        self.assertFalse(app.is_initialized)


if __name__ == "__main__":
    unittest.main()
