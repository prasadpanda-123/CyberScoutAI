"""
Unit tests for SMTP retry mechanisms.
"""

import unittest
from unittest.mock import MagicMock

from src.notifier.exceptions import RetryExceeded, SMTPError
from src.notifier.retry import retry_smtp


class TestSMTPRetry(unittest.TestCase):
    def test_retry_success_after_failure(self):
        call_count = 0

        @retry_smtp(attempts=3, delay_secs=0.01)
        def mock_send():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise SMTPError("Temporary SMTP server error")
            return "delivered"

        res = mock_send()
        self.assertEqual(res, "delivered")
        self.assertEqual(call_count, 2)

    def test_retry_exhausted_exception(self):
        call_count = 0

        @retry_smtp(attempts=3, delay_secs=0.01)
        def mock_send_fail():
            nonlocal call_count
            call_count += 1
            raise SMTPError("Persistent connection failure")

        with self.assertRaises(RetryExceeded):
            mock_send_fail()
        self.assertEqual(call_count, 3)


if __name__ == "__main__":
    unittest.main()
