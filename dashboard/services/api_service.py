"""
API Service wrapping backend actions (scan triggers, scheduler commands, email test dispatch, report queries, logs).
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import text

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
        """Triggers asynchronous background scan job returning immediately."""
        from src.automation.job_manager import scan_job_manager
        job = scan_job_manager.start_scan_job(dry_run=dry_run, db_manager=self.db_manager)
        return {
            "success": True,
            "job_id": job.job_id,
            "status": "started",
            "message": "Scan job initialized and running in background.",
        }

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Queries background scan job status dictionary by job_id."""
        from src.automation.job_manager import scan_job_manager
        return scan_job_manager.get_job(job_id)

    def send_test_email(self) -> Dict[str, Any]:
        """Triggers test notification email digest safely."""
        try:
            res = self.email_client.send_daily_digest(send_empty=True)
            return {"success": True, "status": "completed", "details": res, "message": "Test email sent successfully."}
        except Exception as e:
            return {"success": False, "status": "failed", "error": str(e)}

    def send_daily_report_now(self) -> Dict[str, Any]:
        """Executes the exact daily report email logic as scheduled midnight run."""
        try:
            res = self.email_client.send_daily_digest(send_empty=True)
            return {
                "success": True,
                "status": "completed",
                "details": res,
                "message": "Daily report digest email generated and sent successfully."
            }
        except Exception as e:
            return {"success": False, "status": "failed", "error": str(e)}

    def clear_old_opportunities(self, days: int = 30) -> Dict[str, Any]:
        """Deletes opportunities discovered more than specified days ago."""
        try:
            from src.database.opportunity_repository import OpportunityRepository
            opp_repo = OpportunityRepository(db_manager=self.db_manager)
            deleted_count = opp_repo.delete_old_records(days=days)
            return {
                "success": True,
                "status": "completed",
                "deleted_count": deleted_count,
                "message": f"Cleaned up {deleted_count} opportunities older than {days} days."
            }
        except Exception as e:
            return {"success": False, "status": "failed", "error": str(e)}

    def refresh_analytics(self) -> Dict[str, Any]:
        """Recalculates provider statistics and performance metrics in database."""
        try:
            from src.database.provider_statistics import ProviderStatisticsManager
            stats_mgr = ProviderStatisticsManager(db_manager=self.db_manager)
            stats_mgr.recalculate_all()
            return {
                "success": True,
                "status": "completed",
                "message": "Analytics metrics and provider performance stats recalculated successfully."
            }
        except Exception as e:
            return {"success": False, "status": "failed", "error": str(e)}

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
        return {"success": True, "status": "paused", "message": "Scheduler background service paused."}

    def resume_scheduler(self) -> Dict[str, Any]:
        """Resumes scheduler background daemon service."""
        self.automation_engine.scheduler_service.start()
        return {"success": True, "status": "running", "message": "Scheduler background service resumed."}

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
        """Returns historical timeseries and category distribution chart datasets using SQLAlchemy."""
        engine = self.db_manager.get_engine()
        with engine.connect() as conn:
            # 1. Daily collection trend (past 30 days)
            daily_rows = conn.execute(text("""
                SELECT discovered_date, COUNT(*) as count 
                FROM Opportunities 
                WHERE (is_rejected = 0 OR is_rejected IS NULL) AND discovered_date IS NOT NULL 
                GROUP BY discovered_date 
                ORDER BY discovered_date ASC 
                LIMIT 30
            """)).mappings().all()
            daily_dates = [str(r["discovered_date"]) for r in daily_rows]
            daily_counts = [r["count"] for r in daily_rows]

            # 2. Category distribution
            cat_rows = conn.execute(text("""
                SELECT category, COUNT(*) as count 
                FROM Opportunities 
                WHERE (is_rejected = 0 OR is_rejected IS NULL) 
                GROUP BY category 
                ORDER BY count DESC
            """)).mappings().all()
            categories = [r["category"] for r in cat_rows]
            category_counts = [r["count"] for r in cat_rows]

            # 3. Source reliability & collection volume
            source_rows = conn.execute(text("""
                SELECT source_id, COUNT(*) as count 
                FROM Opportunities 
                WHERE (is_rejected = 0 OR is_rejected IS NULL) 
                GROUP BY source_id 
                ORDER BY count DESC 
                LIMIT 10
            """)).mappings().all()
            sources = [r["source_id"] for r in source_rows]
            source_counts = [r["count"] for r in source_rows]

            return {
                "daily_trend": {"dates": daily_dates, "counts": daily_counts},
                "categories": {"labels": categories, "values": category_counts},
                "sources": {"labels": sources, "values": source_counts},
            }
