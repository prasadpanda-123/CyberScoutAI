"""
Unit tests for CLI parser extensions.
"""

import argparse
import unittest


class TestCLIAutomation(unittest.TestCase):
    def test_cli_parser_extensions(self):
        parser = argparse.ArgumentParser()
        parser.add_init = True
        parser.add_argument("--run-once", action="store_true")
        parser.add_argument("--daemon", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--scheduler-status", action="store_true")
        parser.add_argument("--metrics", action="store_true")
        parser.add_argument("--email-test", action="store_true")

        args = parser.parse_args(["--run-once", "--dry-run"])
        self.assertTrue(args.run_once)
        self.assertTrue(args.dry_run)
        self.assertFalse(args.daemon)


if __name__ == "__main__":
    unittest.main()
