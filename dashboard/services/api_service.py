"""
API Service wrapping backend actions (scan triggers, scheduler commands, email test dispatch).
"""

from typing import Any, Dict, Optional

from src.automation.engine import AutomationEngine
from src.database.connection import DatabaseManager
from src.notifier.email_client import EmailClient

class APIService:
    """Invokes backend commands on behalf of REST API routes."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.automation_engine = AutomationEngine(db_manager=self.db_manager)
        self.email_client = EmailClient(db_manager=self.db_manager)

    def trigger_scan(self, dry_run: bool = False) -> Dict[str, Any]:
        """Triggers single scan pipeline execution using run_pipeline_once."""
        from src.automation.pipeline import run_pipeline_once
        return run_pipeline_once(dry_run=dry_run, db_manager=self.db_manager)

    def send_test_email(self) -> Dict[str, Any]:
        """Triggers test notification email digest."""
        return self.email_client.send_daily_digest()

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Returns background scheduler & daily report scheduler status."""
        from src.scheduler.daily_report_scheduler import DailyReportScheduler
        daily_sched = DailyReportScheduler(db_manager=self.db_manager)
        status = daily_sched.get_status()
        status["background_daemon"] = self.automation_engine.scheduler_service.get_status()
        return status

    def pause_scheduler(self) -> Dict[str, Any]:
        """Pauses scheduler background daemon service."""
        self.automation_engine.scheduler_service.stop()
        return {"status": "paused", "message": "Scheduler background service paused."}

    def resume_scheduler(self) -> Dict[str, Any]:
        """Resumes scheduler background daemon service."""
        self.automation_engine.scheduler_service.start()
        return {"status": "running", "message": "Scheduler background service resumed."}
