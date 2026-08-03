"""
Report Generator for CyberScout AI Knowledge Base.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional

from src.database.analytics import AnalyticsEngine
from src.database.connection import DatabaseManager


class ReportGenerator:
    """
    Generates structured JSON reports for daily, weekly, and monthly summaries.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        analytics_engine: Optional[AnalyticsEngine] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.analytics_engine = analytics_engine or AnalyticsEngine(db_manager=self.db_manager)

    def generate_daily_report(self) -> Dict[str, Any]:
        """
        Generates daily summary report dictionary.

        Returns:
            Report dictionary structure.
        """
        summary = self.analytics_engine.generate_analytics_summary()
        now_str = datetime.now(timezone.utc).isoformat()

        return {
            "report_type": "daily_summary",
            "generated_at": now_str,
            "metrics": summary,
        }

    def generate_daily_report_json(self) -> str:
        """Renders daily report to formatted JSON string."""
        report_dict = self.generate_daily_report()
        return json.dumps(report_dict, indent=2)
