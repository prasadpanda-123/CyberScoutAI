"""
CSV Report Generator for CyberScout AI.

Generates structured, UTF-8 encoded CSV files for direct opening in Microsoft Excel and data analytical workflows.
"""

import csv
from pathlib import Path
from typing import List
from src.core.logging import get_logger
from src.models.opportunity import Opportunity
from src.reporting.report_models import ReportPayload

logger = get_logger(__name__)


class CSVReportGenerator:
    """
    Generates CyberScout_Report_YYYY_MM_DD.csv adhering to the 15-column schema.
    """

    CSV_HEADERS: List[str] = [
        "Category",
        "Priority",
        "Title",
        "Organization",
        "Description",
        "Confidence Score",
        "Quality Score",
        "Verification",
        "Published Date",
        "Deadline",
        "Location",
        "Skills",
        "Tags",
        "Source",
        "Original URL",
    ]

    def generate(self, payload: ReportPayload, output_dir: Path) -> Path:
        """
        Generates CSV report file.

        Args:
            payload: ReportPayload model containing opportunities and date string.
            output_dir: Target output directory (e.g. reports/csv/).

        Returns:
            Path object to generated CSV file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"CyberScout_Report_{payload.date_str}.csv"
        filepath = output_dir / filename

        rows_count = 0
        try:
            with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(self.CSV_HEADERS)

                for opp in payload.all_opportunities:
                    # Extraction helpers
                    category = opp.category or "Other"
                    raw_data = getattr(opp, "raw_data", {}) or {}
                    if not isinstance(raw_data, dict):
                        raw_data = {}

                    priority = raw_data.get("priority", "P2" if opp.score >= 60 else "P3")
                    title = opp.title or "Untitled Opportunity"
                    organization = opp.provider or opp.company or "Unknown Organization"
                    description = opp.description or ""
                    confidence = round(getattr(opp, "confidence_score", 0.0) or 0.0, 1)
                    quality = round(getattr(opp, "quality_score", 0.0) or 0.0, 1)
                    verification = getattr(opp, "verification_status", "VERIFIED") or "VERIFIED"
                    published = opp.published_date or opp.discovered_date or ""
                    deadline = opp.deadline or "N/A"
                    location = opp.location or ("Remote" if opp.remote else "Global")
                    
                    # Extract skills & tags
                    tags_list = opp.tags if isinstance(opp.tags, list) else []
                    tags_str = ", ".join(tags_list)
                    skills_str = raw_data.get("skills", tags_str)
                    source = opp.source_id or "CyberScout Collector"
                    url = opp.url or ""

                    row = [
                        category,
                        priority,
                        title,
                        organization,
                        description,
                        confidence,
                        quality,
                        verification,
                        published,
                        deadline,
                        location,
                        skills_str,
                        tags_str,
                        source,
                        url,
                    ]
                    writer.writerow(row)
                    rows_count += 1

            file_size_kb = round(filepath.stat().st_size / 1024, 2)
            logger.info(f"Generated CSV report '{filepath.name}' ({rows_count} rows, {file_size_kb} KB).")
            return filepath

        except Exception as e:
            logger.error(f"Failed to generate CSV report '{filename}': {e}")
            raise
