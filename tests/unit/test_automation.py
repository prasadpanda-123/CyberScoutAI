"""
Unit tests for the Automation Engine (Phase 9).
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock

from src.database.connection import DatabaseManager
from src.automation.engine import AutomationEngine
from src.automation.pipeline import PipelineRunner
from src.automation.scheduler import SchedulerService


class TestAutomationEngine(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()

    def tearDown(self):
        self.db_manager.close()

    def test_run_once(self):
        pipeline_mock = MagicMock(spec=PipelineRunner)
        pipeline_mock.run_pipeline.return_value = {
            "run_id": "test-run",
            "items_collected": 5,
            "items_ranked": 3,
        }

        engine = AutomationEngine(
            db_manager=self.db_manager,
            pipeline_runner=pipeline_mock,
        )

        res = engine.run_once(dry_run=True)
        self.assertEqual(res["run_id"], "test-run")
        self.assertEqual(res["items_collected"], 5)


if __name__ == "__main__":
    unittest.main()
