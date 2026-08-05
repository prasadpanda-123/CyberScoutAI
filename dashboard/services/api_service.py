"""
API Service wrapping backend actions (scan triggers, scheduler commands, email test dispatch, report queries, logs).
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.automation.engine import AutomationEngine
from src.core.constants import REPORTS_DIR
from src.database.connection import DatabaseManager
from src.database.log_repository import LogRepository
from src.notifier.email_client import EmailClient


class APIService:
    """Invokes backend commands on behalf of REST API routes."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.automation_engine = AutomationEngine(db_manager=self.db_manager)
        self.email_client = EmailClient(db_manager=self.db_manager)
        self.log_repo = LogRepository(db_manager=self.db_manager)

    def trigger_scan(self, dry_run: bool = False) -> Dict[str, Any]:
        """Triggers single scan pipeline execution using run_pipeline_once."""
        from src.automation.pipeline import run_pipeline_once
        return run_pipeline_once(dry_run=dry_run, db_manager=self.db_manager)

    def send_test_email(self) -> Dict[str, Any]:
        """Triggers test notification email digest safely."""
        try:
            return self.email_client.send_daily_digest(send_empty=True)
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def check_smtp_health(self) -> Dict[str, Any]:
        """Runs pre-flight email provider diagnostics."""
        try:
            return self.email_client.check_smtp_connectivity()
        except Exception as e:
            return {"status": "failed", "stage": "CONFIG", "reason": str(e), "is_healthy": False}

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

    def get_reports_list(self) -> List[Dict[str, Any]]:
        """Scans REPORTS_DIR and returns details of all generated DOCX & CSV report files."""
        reports_dir = REPORTS_DIR
        if not reports_dir.exists():
            return []

        reports_list = []
        for p in sorted(reports_dir.glob("*.*"), key=os.path.getmtime, reverse=True):
            if p.suffix.lower() not in (".docx", ".csv"):
                continue
            stat = p.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            size_kb = round(stat.st_size / 1024, 1)

            reports_list.append({
                "filename": p.name,
                "file_type": p.suffix[1:].upper(),
                "created_at": mtime,
                "size_kb": size_kb,
                "download_url": f"/reports/download/{p.name}",
            })
        return reports_list

    def get_logs(
        self,
        level: Optional[str] = None,
        module: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Queries structured logs from LogRepository."""
        return self.log_repo.query_logs(
            level=level,
            module=module,
            search_query=search_query,
            page=page,
            limit=limit,
        )

    def get_charts_data(self) -> Dict[str, Any]:
        """Returns 100% real historical timeseries and category distribution chart datasets."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            # 1. Daily collection trend (past 30 days)
            cursor.execute("""
                SELECT discovered_date, COUNT(*) as count 
                FROM Opportunities 
                WHERE is_rejected = 0 AND discovered_date IS NOT NULL 
                GROUP BY discovered_date 
                ORDER BY discovered_date ASC 
                LIMIT 30
            """)
            daily_rows = cursor.fetchall()
            daily_dates = [r["discovered_date"] for r in daily_rows]
            daily_counts = [r["count"] for r in daily_rows]

            # 2. Category distribution
            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM Opportunities 
                WHERE is_rejected = 0 
                GROUP BY category 
                ORDER BY count DESC
            """)
            cat_rows = cursor.fetchall()
            categories = [r["category"] for r in cat_rows]
            category_counts = [r["count"] for r in cat_rows]

            # 3. Source reliability & collection volume
            cursor.execute("""
                SELECT source_id, COUNT(*) as count 
                FROM Opportunities 
                WHERE is_rejected = 0 
                GROUP BY source_id 
                ORDER BY count DESC 
                LIMIT 10
            """)
            source_rows = cursor.fetchall()
            sources = [r["source_id"] for r in source_rows]
            source_counts = [r["count"] for r in source_rows]

            return {
                "daily_trend": {"dates": daily_dates, "counts": daily_counts},
                "categories": {"labels": categories, "values": category_counts},
                "sources": {"labels": sources, "values": source_counts},
            }
        finally:
            cursor.close()
