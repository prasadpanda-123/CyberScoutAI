"""
Unit tests for RunMetrics.
"""

import unittest

from src.automation.metrics import RunMetrics


class TestRunMetrics(unittest.TestCase):
    def test_to_dict(self):
        metrics = RunMetrics(run_id="run-123")
        metrics.planning_time = 0.5
        metrics.collection_time = 1.2
        metrics.processing_time = 0.3
        metrics.ranking_time = 0.1
        metrics.db_update_time = 0.2
        metrics.notification_time = 0.4
        metrics.total_time = 2.7

        dct = metrics.to_dict()
        self.assertEqual(dct["run_id"], "run-123")
        self.assertEqual(dct["planning_time_sec"], 0.5)
        self.assertEqual(dct["collection_time_sec"], 1.2)
        self.assertEqual(dct["total_time_sec"], 2.7)


if __name__ == "__main__":
    unittest.main()
