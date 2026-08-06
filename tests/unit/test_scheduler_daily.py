"""
Unit Tests for Phase 12.3 Daily Scheduled Email Delivery System.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.core.exceptions import ConfigurationError
from src.database.connection import DatabaseManager
from src.database.scheduler_repository import SchedulerRepository
from src.scheduler.daily_report_scheduler import DailyReportScheduler


class TestDailyReportScheduler(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sched.db"
        self.db_mgr = DatabaseManager(db_path=self.db_path)
        self.db_mgr.initialize_database()
        self.scheduler_repo = SchedulerRepository(db_manager=self.db_mgr)
        # Reset scheduler state to ensure clean test isolation (shared in-memory DB)
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scheduler_state")
        conn.commit()
        cursor.close()

    def tearDown(self):
        self.db_mgr.close()
        self.temp_dir.cleanup()

    def test_database_persistence_and_initialization(self):
        """Verify scheduler_state table initialization and repository persistence."""
        state = self.scheduler_repo.get_state()
        self.assertEqual(state["last_email_sent"], "")
        self.assertEqual(state["last_pipeline_run"], "")

        # Update last email sent
        self.scheduler_repo.update_last_email_sent("2026-08-05")
        updated_state = self.scheduler_repo.get_state()
        self.assertEqual(updated_state["last_email_sent"], "2026-08-05")

        # Update last pipeline run
        self.scheduler_repo.update_last_pipeline_run("2026-08-05T12:00:00Z")
        final_state = self.scheduler_repo.get_state()
        self.assertEqual(final_state["last_email_sent"], "2026-08-05")
        self.assertEqual(final_state["last_pipeline_run"], "2026-08-05T12:00:00Z")

    @patch.dict(os.environ, {
        "EMAIL_ENABLED": "true",
        "REPORT_TIME": "00:00",
        "TIMEZONE": "Asia/Kolkata",
        "REPORT_FREQUENCY": "daily",
        "SEND_EMPTY_REPORT": "false",
    })
    def test_configuration_loading_and_defaults(self):
        """Verify reading and parsing configuration from environment variables."""
        sched = DailyReportScheduler(db_manager=self.db_mgr)
        self.assertTrue(sched.email_enabled)
        self.assertEqual(sched.report_time_str, "00:00")
        self.assertEqual(sched.timezone_name, "Asia/Kolkata")
        self.assertEqual(sched.report_frequency, "daily")
        self.assertFalse(sched.send_empty_report)

    @patch.dict(os.environ, {"REPORT_TIME": "invalid_time"})
    def test_configuration_validation_invalid_time(self):
        """Verify ConfigurationError raised on invalid REPORT_TIME format."""
        with self.assertRaises(ConfigurationError):
            DailyReportScheduler(db_manager=self.db_mgr)

    @patch.dict(os.environ, {"TIMEZONE": "Invalid/Timezone_Name"})
    def test_configuration_validation_invalid_timezone(self):
        """Verify ConfigurationError raised on invalid TIMEZONE."""
        with self.assertRaises(ConfigurationError):
            DailyReportScheduler(db_manager=self.db_mgr)

    def test_timezone_calculations(self):
        """Verify timezone-aware datetime calculations and next run time."""
        sched = DailyReportScheduler(db_manager=self.db_mgr)
        now_tz = sched.get_now()
        self.assertIsNotNone(now_tz.tzinfo)

        today_str = sched.get_today_date_str()
        self.assertTrue(len(today_str) == 10)  # YYYY-MM-DD

        next_run = sched.get_next_run_time()
        self.assertGreater(next_run, now_tz)

    def test_duplicate_prevention(self):
        """Verify that should_send_today returns False if last_email_sent equals today."""
        sched = DailyReportScheduler(db_manager=self.db_mgr)
        today_str = sched.get_today_date_str()

        # Initially True
        self.assertTrue(sched.should_send_today())

        # Update last email sent to today
        self.scheduler_repo.update_last_email_sent(today_str)

        # Now should be False (prevent duplicate email)
        self.assertFalse(sched.should_send_today())

    def test_restart_recovery(self):
        """Verify restart recovery reads persistent scheduler_state from database."""
        today_str = "2026-08-05"
        self.scheduler_repo.update_last_email_sent(today_str)

        # Simulate app restart by instantiating new DailyReportScheduler
        new_sched = DailyReportScheduler(db_manager=self.db_mgr)
        state = new_sched.scheduler_repo.get_state()
        self.assertEqual(state["last_email_sent"], today_str)

    @patch("src.automation.pipeline.PipelineRunner.run_pipeline")
    @patch("src.notifier.email_client.EmailClient.send_daily_digest")
    def test_midnight_workflow_success(self, mock_send_email, mock_run_pipeline):
        """Verify end-to-end midnight workflow execution and DB state update."""
        mock_run_pipeline.return_value = {"status": "success", "items_collected": 10, "items_ranked": 5}
        mock_send_email.return_value = {"status": "success", "message_id": "msg-123"}

        sched = DailyReportScheduler(db_manager=self.db_mgr)
        today_str = sched.get_today_date_str()

        res = sched.run_midnight_workflow(force=True)
        self.assertEqual(res["status"], "success")

        # Verify state updated in DB
        state = self.scheduler_repo.get_state()
        self.assertEqual(state["last_email_sent"], today_str)

    @patch("src.automation.pipeline.PipelineRunner.run_pipeline")
    @patch("src.notifier.email_client.EmailClient.send_daily_digest")
    def test_email_failure_retry_handling(self, mock_send_email, mock_run_pipeline):
        """Verify that on email failure, last_email_sent is NOT updated to allow retries."""
        mock_run_pipeline.return_value = {"status": "success", "items_collected": 10, "items_ranked": 5}
        mock_send_email.return_value = {"status": "failed", "error": "SMTP Connection Failed"}

        sched = DailyReportScheduler(db_manager=self.db_mgr)

        res = sched.run_midnight_workflow(force=True)
        self.assertEqual(res["status"], "failed")

        # Verify last_email_sent was NOT updated to today
        state = self.scheduler_repo.get_state()
        self.assertEqual(state["last_email_sent"], "")

    @patch("src.automation.pipeline.PipelineRunner.run_pipeline")
    @patch("src.notifier.email_client.EmailClient.send_daily_digest")
    def test_empty_report_behavior(self, mock_send_email, mock_run_pipeline):
        """Verify empty report handling when SEND_EMPTY_REPORT is true vs false."""
        mock_run_pipeline.return_value = {"status": "success", "items_collected": 0, "items_ranked": 0}

        # Case 1: send_empty_report = False
        sched_false = DailyReportScheduler(db_manager=self.db_mgr)
        sched_false.send_empty_report = False
        mock_send_email.return_value = {"status": "skipped", "message": "No active opportunities"}

        res1 = sched_false.run_midnight_workflow(force=True)
        self.assertEqual(res1["status"], "success")
        mock_send_email.assert_called_with(send_empty=False)

        # Case 2: send_empty_report = True
        sched_true = DailyReportScheduler(db_manager=self.db_mgr)
        sched_true.send_empty_report = True
        mock_send_email.return_value = {"status": "success", "message_id": "empty-123"}

        res2 = sched_true.run_midnight_workflow(force=True)
        self.assertEqual(res2["status"], "success")
        mock_send_email.assert_called_with(send_empty=True)

    def test_scheduler_status_output(self):
        """Verify get_status returns expected keys."""
        sched = DailyReportScheduler(db_manager=self.db_mgr)
        status = sched.get_status()

        self.assertIn("enabled", status)
        self.assertIn("frequency", status)
        self.assertIn("timezone", status)
        self.assertIn("report_time", status)
        self.assertIn("next_run", status)
        self.assertIn("last_email_sent", status)
        self.assertIn("last_pipeline_run", status)
        self.assertIn("healthy", status)


if __name__ == "__main__":
    unittest.main()
