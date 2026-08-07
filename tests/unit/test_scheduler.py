"""
Unit tests for background SchedulerService.
"""

import time
import unittest

from src.automation.scheduler import SchedulerService


class TestSchedulerService(unittest.TestCase):
    def test_add_and_trigger_job(self):
        scheduler = SchedulerService()
        scheduler.interval_seconds = 0.1  # 0.1 second interval

        triggered = False

        def mock_callback():
            nonlocal triggered
            triggered = True

        scheduler.add_job("test_job", mock_callback)
        scheduler.start()

        # Wait to allow job trigger
        time.sleep(0.3)
        scheduler.stop()

        self.assertTrue(triggered)


if __name__ == "__main__":
    unittest.main()
