"""
Unit tests for PipelineRunner.
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock

from src.database.connection import DatabaseManager
from src.collectors.manager import CollectorManager
from src.collectors.result import CollectorResult
from src.intelligence.search_planner import SearchPlanner
from src.intelligence.planner_models import SearchPlan, SearchTask
from src.automation.pipeline import PipelineRunner
from src.notifier.email_client import EmailClient


class TestPipelineRunner(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_path=Path(":memory:"))
        self.db_manager.initialize_database()

    def tearDown(self):
        self.db_manager.close()

    def test_run_pipeline_success(self):
        planner_mock = MagicMock(spec=SearchPlanner)
        plan = SearchPlan(
            plan_id="plan-1",
            tasks=[
                SearchTask(
                    source_id="sans",
                    query_text="penetration testing",
                    target_url="https://www.sans.org/feed.xml",
                    category="training",
                    collection_method="rss",
                )
            ],
        )
        planner_mock.create_search_plan.return_value = plan

        collector_mock = MagicMock(spec=CollectorManager)
        collector_mock.execute_plan.return_value = [
            CollectorResult(source_id="sans", status="success", items=[], errors=[])
        ]

        email_mock = MagicMock(spec=EmailClient)
        email_mock.send_daily_digest.return_value = {"status": "success"}

        runner = PipelineRunner(
            db_manager=self.db_manager,
            search_planner=planner_mock,
            collector_manager=collector_mock,
            email_client=email_mock,
        )

        res = runner.run_pipeline(dry_run=True)
        self.assertIn("run_id", res)
        self.assertEqual(res["items_collected"], 0)
        self.assertEqual(res["items_ranked"], 0)


if __name__ == "__main__":
    unittest.main()
