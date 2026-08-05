"""
Daily Scheduled Email Delivery Engine (Midnight Report) for CyberScout AI.

Manages daily 00:00 (configurable) email report execution, timezone handling,
restart recovery, duplicate prevention, and database state updates.
"""

from datetime import datetime, time as dtime, timedelta, timezone
import os
import re
import threading
import time
from typing import Any, Dict, Optional
import zoneinfo

from src.core.config import config
from src.core.exceptions import ConfigurationError
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.scheduler_repository import SchedulerRepository
from src.automation.pipeline import PipelineRunner
from src.notifier.email_client import EmailClient

logger = get_logger(__name__)


def _parse_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return default


class DailyReportScheduler:
    """
    Timezone-aware daily report scheduler ensuring single daily email delivery at REPORT_TIME.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        pipeline_runner: Optional[PipelineRunner] = None,
        email_client: Optional[EmailClient] = None,
        scheduler_repo: Optional[SchedulerRepository] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.pipeline_runner = pipeline_runner or PipelineRunner(db_manager=self.db_manager)
        self.email_client = email_client or EmailClient(db_manager=self.db_manager)
        self.scheduler_repo = scheduler_repo or SchedulerRepository(db_manager=self.db_manager)

        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Load & validate configuration
        self.reload_configuration()

    def reload_configuration(self) -> None:
        """Loads and validates scheduler settings from environment variables or config files."""
        # 1. EMAIL_ENABLED
        env_email = os.getenv("EMAIL_ENABLED")
        self.email_enabled = _parse_bool(env_email, config.get("email_enabled", True))

        # 2. REPORT_TIME (format HH:MM)
        self.report_time_str = (os.getenv("REPORT_TIME") or config.get("report_time", "00:00")).strip()
        if not re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", self.report_time_str):
            raise ConfigurationError(f"Invalid REPORT_TIME format '{self.report_time_str}'. Expected HH:MM.")

        hours, minutes = map(int, self.report_time_str.split(":"))
        self.target_time = dtime(hour=hours, minute=minutes)

        # 3. TIMEZONE
        self.timezone_name = (os.getenv("TIMEZONE") or config.get("timezone", "Asia/Kolkata")).strip()
        try:
            self.tz = zoneinfo.ZoneInfo(self.timezone_name)
        except Exception as e:
            raise ConfigurationError(f"Invalid TIMEZONE '{self.timezone_name}': {e}", original_exception=e)

        # 4. REPORT_FREQUENCY
        self.report_frequency = (os.getenv("REPORT_FREQUENCY") or config.get("report_frequency", "daily")).strip().lower()
        if self.report_frequency not in ("daily", "weekly", "monthly"):
            raise ConfigurationError(f"Unsupported REPORT_FREQUENCY '{self.report_frequency}'. Allowed: daily, weekly, monthly.")

        # 5. SEND_EMPTY_REPORT
        env_send_empty = os.getenv("SEND_EMPTY_REPORT")
        self.send_empty_report = _parse_bool(env_send_empty, config.get("send_empty_report", False))

        logger.info(
            f"[Scheduler Config] Enabled: {self.email_enabled}, Report Time: {self.report_time_str}, "
            f"Timezone: {self.timezone_name}, Frequency: {self.report_frequency}, Send Empty: {self.send_empty_report}"
        )

    def get_now(self) -> datetime:
        """Returns current timezone-aware datetime in configured timezone."""
        return datetime.now(self.tz)

    def get_today_date_str(self) -> str:
        """Returns YYYY-MM-DD formatted date string in configured timezone."""
        return self.get_now().strftime("%Y-%m-%d")

    def get_next_run_time(self) -> datetime:
        """
        Calculates the next scheduled run occurrence in the configured timezone.
        """
        now = self.get_now()
        candidate = datetime.combine(now.date(), self.target_time, tzinfo=self.tz)

        if candidate <= now:
            candidate += timedelta(days=1)

        return candidate

    def should_send_today(self) -> bool:
        """
        Checks SQLite scheduler_state to ensure no email report has been sent yet today.

        Returns:
            True if today's email has not been sent, False otherwise.
        """
        state = self.scheduler_repo.get_state()
        last_sent = state.get("last_email_sent", "")
        today_str = self.get_today_date_str()
        return last_sent != today_str

    def run_midnight_workflow(self, force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executes the midnight pipeline and email delivery workflow.

        Sequence:
            1. Validate duplicate prevention (unless force=True)
            2. Run complete scan & collection pipeline
            3. Compile HTML report digest
            4. Send Email via SMTP
            5. Persist updated last_email_sent to SQLite scheduler_state

        Args:
            force: If True, bypasses schedule and duplicate prevention checks (for manual test mode).
            dry_run: If True, bypasses database writes and SMTP delivery.

        Returns:
            Execution summary dictionary.
        """
        start_mono = time.time()
        now_tz = self.get_now()
        today_str = now_tz.strftime("%Y-%m-%d")
        now_iso = now_tz.isoformat()

        state = self.scheduler_repo.get_state()
        last_sent = state.get("last_email_sent", "Never")

        logger.info("===========================================================================")
        logger.info("[Scheduler] Executing Daily Report Workflow")
        logger.info("===========================================================================")
        logger.info(f"[Scheduler] Current Time   : {now_tz.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"[Scheduler] Configured Time: {self.report_time_str}")
        logger.info(f"[Scheduler] Timezone        : {self.timezone_name}")
        logger.info(f"[Scheduler] Last Email Sent : {last_sent}")

        if not force and not self.should_send_today():
            logger.info(f"[Scheduler] Decision       : Report already sent today ({today_str}). Skipping.")
            return {"status": "skipped", "reason": "Already sent today", "last_email_sent": last_sent}

        if not force and not self.email_enabled:
            logger.info("[Scheduler] Decision       : EMAIL_ENABLED is False. Skipping email dispatch.")
            return {"status": "disabled", "reason": "EMAIL_ENABLED is False"}

        logger.info("[Scheduler] Decision       : Proceeding with Pipeline Scan & Email Delivery.")

        # Step 1: Run complete collection & ranking pipeline (without immediate email dispatch)
        logger.info("[Scheduler] Pipeline Started...")
        pipe_result = self.pipeline_runner.run_pipeline(dry_run=dry_run, send_email=False)
        logger.info(f"[Scheduler] Pipeline Finished. Items collected: {pipe_result.get('items_collected', 0)}, Ranked: {pipe_result.get('items_ranked', 0)}")

        # Step 2: Email Generation & Dispatch
        email_result = {"status": "skipped"}
        if not dry_run:
            logger.info("[Scheduler] Generating and dispatching email report...")
            email_result = self.email_client.send_daily_digest(send_empty=self.send_empty_report)

        email_status = email_result.get("status")

        # Step 3: Update Scheduler Persistence State
        if not dry_run:
            if email_status == "success":
                self.scheduler_repo.update_last_email_sent(today_str, pipeline_run_time=now_iso)
                logger.info("[Scheduler] Email Sent. Database Updated (last_email_sent).")
            elif email_status == "skipped":
                # Mark today's pipeline run finished to prevent infinite retry loops on 0 new items when send_empty=False
                self.scheduler_repo.update_last_email_sent(today_str, pipeline_run_time=now_iso)
                logger.info("[Scheduler] Email Skipped (0 items, send_empty=False). Database Updated.")
            else:
                logger.error(f"[Scheduler] Email Delivery Failed ({email_result.get('error')}). last_email_sent NOT updated.")

        duration = round(time.time() - start_mono, 2)
        logger.info(f"[Scheduler] Daily Report Workflow Complete in {duration}s. Status: {email_status}")
        logger.info("===========================================================================")

        return {
            "status": "success" if email_status in ("success", "skipped") else "failed",
            "email_status": email_status,
            "pipeline_result": pipe_result,
            "email_result": email_result,
            "execution_duration_sec": duration,
            "last_email_sent": today_str if email_status in ("success", "skipped") else last_sent,
        }

    def start(self) -> None:
        """Starts background daemon scheduler loop in a separate thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"DailyReportScheduler background thread started ({self.report_time_str} {self.timezone_name}).")

    def stop(self) -> None:
        """Stops background daemon thread."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("DailyReportScheduler background thread stopped.")

    def _run_loop(self) -> None:
        """Daemon check loop executing daily report workflow when target REPORT_TIME is reached."""
        while not self._stop_event.is_set():
            try:
                now_tz = self.get_now()
                now_time_str = now_tz.strftime("%H:%M")
                if now_time_str == self.report_time_str and self.should_send_today():
                    self.run_midnight_workflow(force=False, dry_run=False)
                    # Sleep 60s after trigger to avoid double firing during the same minute
                    time.sleep(60)
            except Exception as e:
                logger.error(f"Error in DailyReportScheduler loop: {e}", exc_info=True)

            # Check every 10 seconds
            time.sleep(10)

    def get_status(self) -> Dict[str, Any]:
        """
        Returns full diagnostic status dictionary of the scheduler.

        Returns:
            Dictionary matching requirement parameters.
        """
        state = self.scheduler_repo.get_state()
        next_run = self.get_next_run_time()

        return {
            "enabled": self.email_enabled,
            "running": self._running,
            "frequency": self.report_frequency,
            "timezone": self.timezone_name,
            "report_time": self.report_time_str,
            "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "last_email_sent": state.get("last_email_sent") or "Never",
            "last_pipeline_run": state.get("last_pipeline_run") or "Never",
            "send_empty_report": self.send_empty_report,
            "healthy": True,
        }
