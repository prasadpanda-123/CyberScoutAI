"""
Unit tests for ShutdownHandler.
"""

import unittest

from src.automation.runtime import ShutdownHandler


class TestShutdownHandler(unittest.TestCase):
    def test_callback_registration(self):
        handler = ShutdownHandler()
        called = False

        def mock_callback():
            nonlocal called
            called = True

        handler.register_callback(mock_callback)
        self.assertEqual(len(handler.callbacks), 1)


if __name__ == "__main__":
    unittest.main()
