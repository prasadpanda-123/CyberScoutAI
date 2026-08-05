"""
ReportManager Orchestrator for CyberScout AI Reporting Package.

Coordinates payload building, output directory management, CSV and DOCX generation,
metrics logging, and error resilience.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import time
from typing import Dict, List, Optional

from src.core.constants import PROJECT_ROOT
from src.core.logging import get_logger
from src.models.opportunity import Opportunity
from src.reporting.csv_generator import CSVReportGenerator
from src.reporting.docx_generator import DOCXReportGenerator
from src.reporting.report_models import ReportPayload, ReportResult, ReportSummary

logger = get_logger(__name__)


class ReportManager:
    """
    Central manager for generating DOCX and CSV reports for accepted opportunities.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        csv_generator: Optional[CSVReportGenerator] = None,
        docx_generator: Optional[DOCXReportGenerator] = None,
    ):
        self.base_dir = base_dir or (PROJECT_ROOT / "reports")
        self.csv_dir = self.base_dir / "csv"
        self.docx_dir = self.base_dir / "docx"
        
        self.csv_generator = csv_generator or CSVReportGenerator()
        self.docx_generator = docx_generator or DOCXReportGenerator()

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Creates output directories if they do not exist."""
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.docx_dir.mkdir(parents=True, exist_ok=True)

    def prepare_payload(
        self,
        opportunities: List[Opportunity],
        date_str: Optional[str] = None,
    ) -> ReportPayload:
        """
        Filters accepted opportunities, groups by category, and compiles ReportPayload.

        Args:
            opportunities: List of Opportunity entity models.
            date_str: Optional YYYY_MM_DD formatted date string.

        Returns:
            Populated ReportPayload instance.
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")

        # 1. Filter accepted, non-expired, non-archived opportunities
        accepted = [
            opp for opp in opportunities
            if not opp.is_rejected
            and not getattr(opp, "expired", False)
            and not getattr(opp, "archived", False)
            and getattr(opp, "verification_status", "VERIFIED") != "REJECTED"
        ]

        # 2. Group by category and compute category breakdown counts
        categories: Dict[str, List[Opportunity]] = {}
        summary = ReportSummary()

        for opp in accepted:
            cat = (opp.category or "other").lower().strip()
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(opp)

            if cat == "internship":
                summary.internships += 1
            elif cat == "course":
                summary.courses += 1
            elif cat == "certification":
                summary.certifications += 1
            elif cat == "hackathon":
                summary.hackathons += 1
            elif cat == "ctf":
                summary.ctfs += 1
            elif cat == "scholarship":
                summary.scholarships += 1
            elif cat == "research":
                summary.research += 1
            elif cat in ["security_news", "news"]:
                summary.security_news += 1
            elif cat in ["github_repository", "project"]:
                summary.github_projects += 1
            elif cat in ["tool", "tools"]:
                summary.tools += 1

        summary.total_opportunities = len(accepted)

        return ReportPayload(
            date_str=date_str,
            summary=summary,
            categories=categories,
            all_opportunities=accepted,
        )

    def generate_reports(
        self,
        opportunities: List[Opportunity],
        date_str: Optional[str] = None,
    ) -> ReportResult:
        """
        Generates CSV and DOCX reports with complete error resilience.

        Args:
            opportunities: Accepted opportunities list.
            date_str: Optional date string override.

        Returns:
            ReportResult containing generated attachment paths and telemetry metrics.
        """
        start_time = time.time()
        self._ensure_directories()

        payload = self.prepare_payload(opportunities, date_str=date_str)
        result = ReportResult(rows_written=len(payload.all_opportunities))

        # 1. Generate DOCX Report
        try:
            docx_path = self.docx_generator.generate(payload, self.docx_dir)
            result.docx_path = docx_path
            result.docx_size_bytes = docx_path.stat().st_size
            logger.info(f"ReportManager: Generated DOCX report at '{docx_path}' ({result.docx_size_bytes} bytes).")
        except Exception as e:
            err_msg = f"DOCX report generation failed: {e}"
            logger.error(f"ReportManager: {err_msg}")
            result.errors.append(err_msg)

        # 2. Generate CSV Report
        try:
            csv_path = self.csv_generator.generate(payload, self.csv_dir)
            result.csv_path = csv_path
            result.csv_size_bytes = csv_path.stat().st_size
            logger.info(f"ReportManager: Generated CSV report at '{csv_path}' ({result.csv_size_bytes} bytes).")
        except Exception as e:
            err_msg = f"CSV report generation failed: {e}"
            logger.error(f"ReportManager: {err_msg}")
            result.errors.append(err_msg)

        result.generation_time_sec = round(time.time() - start_time, 3)
        logger.info(
            f"ReportManager completed in {result.generation_time_sec}s. "
            f"Attachments generated: {len(result.attachment_paths)}/2. Errors: {len(result.errors)}"
        )
        return result
