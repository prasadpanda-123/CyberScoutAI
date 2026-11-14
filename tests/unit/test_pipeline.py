"""
Unit tests for PipelineRunner in Phase B.1.
"""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock

from src.automation.pipeline import PipelineRunner, run_pipeline_once
from src.collectors.manager import CollectorManager
from src.collectors.result import CollectorResult
from src.database.connection import DatabaseManager
from src.discovery.discovery_models import DiscoveryRunSummary
from src.discovery.discovery_service import GlobalDiscoveryService
from src.notifier.email_client import EmailClient


class TestPipelineRunner(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()

    def tearDown(self):
        self.db_manager.close()

    def test_run_pipeline_success_with_discovery_service(self):
        discovery_mock = MagicMock(spec=GlobalDiscoveryService)
        discovery_mock.run_discovery.return_value = DiscoveryRunSummary(
            run_id="disc-test-1",
            started_at=datetime.now(timezone.utc).isoformat(),
            candidates_valid=5,
            status="completed",
        )

        collector_mock = MagicMock(spec=CollectorManager)
        collector_mock.execute_plan.return_value = [
            CollectorResult(source_id="sans", status="success", items=[], errors=[])
        ]

        email_mock = MagicMock(spec=EmailClient)
        email_mock.send_daily_digest.return_value = {"status": "success"}

        runner = PipelineRunner(
            db_manager=self.db_manager,
            discovery_service=discovery_mock,
            collector_manager=collector_mock,
            email_client=email_mock,
        )

        res = runner.run_pipeline(dry_run=True)
        self.assertIn("run_id", res)
        self.assertEqual(res["status"], "success")
        self.assertIn("discovery_summary", res)
        self.assertEqual(res["discovery_summary"]["candidates_valid"], 5)
        self.assertEqual(res["items_collected"], 0)
        self.assertEqual(res["items_ranked"], 0)

    def test_passing_search_planner_raises_runtime_error(self):
        dummy_planner = MagicMock()
        with self.assertRaises(RuntimeError) as ctx:
            PipelineRunner(
                db_manager=self.db_manager,
                search_planner=dummy_planner,
            )
        self.assertIn("SearchPlanner has been permanently decommissioned", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx2:
            run_pipeline_once(
                dry_run=True,
                db_manager=self.db_manager,
                search_planner=dummy_planner,
            )
        self.assertIn("SearchPlanner has been permanently decommissioned", str(ctx2.exception))


class TestPipelineStageIsolation(unittest.TestCase):
    def test_discovery_failure_is_reported_without_skipping_later_stages(self):
        discovery = MagicMock()
        discovery.run_discovery.side_effect = RuntimeError("sensitive provider detail")
        extraction = MagicMock()
        classification = MagicMock()
        verifier = MagicMock()
        promotion = MagicMock()

        result = PipelineRunner(
            db_manager=MagicMock(),
            discovery_service=discovery,
            extraction_service=extraction,
            classification_service=classification,
            free_only_verifier=verifier,
            promotion_service=promotion,
        ).run_pipeline(dry_run=True)

        self.assertEqual(result["stage_errors"], ["discovery"])
        self.assertTrue(result["partial"])
        self.assertTrue(result["success"])
        self.assertNotIn("sensitive provider detail", str(result))
        extraction.run_extraction.assert_called_once()
        classification.run_classification.assert_called_once()
        verifier.run_verification.assert_called_once()
        promotion.promote_candidates.assert_called_once()

    def test_partial_stage_summary_marks_pipeline_partial(self):
        discovery = MagicMock()
        discovery.run_discovery.return_value = DiscoveryRunSummary(
            run_id="disc-test-partial",
            started_at=datetime.now(timezone.utc).isoformat(),
            status="partial",
        )

        result = PipelineRunner(
            db_manager=MagicMock(),
            discovery_service=discovery,
            extraction_service=MagicMock(),
            classification_service=MagicMock(),
            free_only_verifier=MagicMock(),
            promotion_service=MagicMock(),
        ).run_pipeline(dry_run=True)

        self.assertEqual(result["stage_errors"], ["discovery"])
        self.assertTrue(result["partial"])
        self.assertEqual(result["discovery_summary"]["status"], "partial")

    def test_collector_exception_does_not_stop_later_stages(self):
        collector_manager = MagicMock()
        collector_manager.execute_plan.side_effect = RuntimeError("collector failure")
        extraction = MagicMock()
        classification = MagicMock()
        verifier = MagicMock()
        promotion = MagicMock()

        result = PipelineRunner(
            db_manager=MagicMock(),
            discovery_service=MagicMock(),
            extraction_service=extraction,
            classification_service=classification,
            free_only_verifier=verifier,
            promotion_service=promotion,
            collector_manager=collector_manager,
        ).run_pipeline(dry_run=True)

        self.assertEqual(result["stage_errors"], ["collectors"])
        self.assertTrue(result["partial"])
        extraction.run_extraction.assert_called_once()
        classification.run_classification.assert_called_once()
        verifier.run_verification.assert_called_once()
        promotion.promote_candidates.assert_called_once()

    def test_failed_collector_result_does_not_mark_healthy_source_failed(self):
        collector_manager = MagicMock()
        collector_manager.execute_plan.return_value = [
            CollectorResult(source_id="healthy", status="success"),
            CollectorResult(source_id="broken", status="failed", errors=["source failure"]),
        ]

        result = PipelineRunner(
            db_manager=MagicMock(),
            discovery_service=MagicMock(),
            extraction_service=MagicMock(),
            classification_service=MagicMock(),
            free_only_verifier=MagicMock(),
            promotion_service=MagicMock(),
            collector_manager=collector_manager,
        ).run_pipeline(dry_run=True)

        self.assertEqual(result["collector_status"], {"healthy": "success", "broken": "failed"})
        self.assertEqual(result["stage_errors"], ["collectors"])
        self.assertTrue(result["partial"])


if __name__ == "__main__":
    unittest.main()
