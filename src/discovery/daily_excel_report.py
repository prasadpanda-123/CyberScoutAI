"""
Daily Excel Report Generator for CyberScout AI (Phase F).

Generates a publication-ready, multi-sheet Excel workbook using openpyxl.
Includes formula injection sanitization, summary metrics, newly promoted
opportunities, and complete verification audit trails.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.core.constants import PROJECT_ROOT
from src.core.logging import get_logger
from src.discovery.promotion_models import DailyReportMetadata
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


def escape_formula_injection(value: Any) -> Any:
    """
    Sanitizes values against spreadsheet formula injection (CSV/Excel Formula Injection).
    Prepends a single apostrophe if string begins with =, +, -, @, tab, or carriage return.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{value}"
    return value


class DailyExcelReportGenerator:
    """
    Generates a structured, 3-sheet Excel workbook for daily cybersecurity intelligence reports.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (PROJECT_ROOT / "reports" / "daily")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Style definitions
        self.header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
        self.header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        self.sub_header_fill = PatternFill(start_color="2B6CB0", end_color="2B6CB0", fill_type="solid")
        self.row_alt_fill = PatternFill(start_color="F7FAFC", end_color="F7FAFC", fill_type="solid")
        self.thin_border = Border(
            left=Side(style="thin", color="CBD5E0"),
            right=Side(style="thin", color="CBD5E0"),
            top=Side(style="thin", color="CBD5E0"),
            bottom=Side(style="thin", color="CBD5E0"),
        )

    def generate_report(
        self,
        metadata: DailyReportMetadata,
        new_opportunities: List[Opportunity],
        verification_details: List[Dict[str, Any]],
        report_date_str: Optional[str] = None,
    ) -> Tuple[Path, str]:
        """
        Creates the daily Excel workbook.

        Args:
            metadata: Aggregated run counts and metrics.
            new_opportunities: List of newly promoted Opportunity entities.
            verification_details: List of Free-Only verification detail records.
            report_date_str: Optional date string (YYYY-MM-DD).

        Returns:
            Tuple of (Path to generated .xlsx, SHA-256 checksum string).
        """
        date_str = report_date_str or metadata.report_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"CyberScout_Daily_Report_{date_str}.xlsx"
        filepath = self.output_dir / filename

        wb = openpyxl.Workbook()

        # -------------------------------------------------------------
        # SHEET 1: Daily Summary
        # -------------------------------------------------------------
        ws_summary = wb.active
        ws_summary.title = "Daily Summary"
        ws_summary.views.sheetView[0].showGridLines = True

        ws_summary["A1"] = "CyberScout AI — Daily Opportunity Discovery Summary"
        ws_summary["A1"].font = Font(name="Calibri", size=14, bold=True, color="1A365D")
        ws_summary["A2"] = f"Report Date: {date_str} (Timezone: {metadata.timezone})"
        ws_summary["A2"].font = Font(name="Calibri", size=11, italic=True, color="4A5568")

        summary_rows = [
            ("Metric / Milestone", "Count / Value", "Description"),
            ("Report Date", date_str, "Date of intelligence scan run"),
            ("Total Discovered Candidates", metadata.total_discovered, "Candidates identified via Tavily Global Discovery"),
            ("Successfully Extracted", metadata.total_extracted, "Full markdown content crawled via Firecrawl API"),
            ("AI Classified Candidates", metadata.total_classified, "Opportunities structured via Groq/Gemini classification"),
            ("Approved Candidates", metadata.total_approved, "Verified free-to-apply opportunities via Phase E Rule Engine"),
            ("Rejected Candidates", metadata.total_rejected, "Candidates with mandatory fees or financial disqualifications"),
            ("Quarantined Candidates", metadata.total_quarantined, "Candidates with missing or uncertain pricing evidence"),
            ("Newly Promoted to Production", metadata.newly_promoted_count, "Genuinely new verified opportunities added to production"),
            ("Existing Opportunities Updated", metadata.existing_updated_count, "Existing production records updated with verified fresh data"),
            ("Total Active Production Database", metadata.total_active_production, "Total active, searchable opportunities in knowledge base"),
        ]

        for r_idx, row_data in enumerate(summary_rows, start=4):
            for c_idx, val in enumerate(row_data, start=1):
                cell = ws_summary.cell(row=r_idx, column=c_idx, value=escape_formula_injection(val))
                cell.border = self.thin_border
                if r_idx == 4:
                    cell.fill = self.header_fill
                    cell.font = self.header_font
                    cell.alignment = Alignment(horizontal="center" if c_idx == 2 else "left", vertical="center")
                else:
                    if r_idx % 2 == 0:
                        cell.fill = self.row_alt_fill
                    cell.font = Font(name="Calibri", size=10)
                    cell.alignment = Alignment(horizontal="center" if c_idx == 2 else "left", vertical="center")

        ws_summary.column_dimensions["A"].width = 35
        ws_summary.column_dimensions["B"].width = 18
        ws_summary.column_dimensions["C"].width = 55

        # -------------------------------------------------------------
        # SHEET 2: New Opportunities
        # -------------------------------------------------------------
        ws_opps = wb.create_sheet(title="New Opportunities")
        ws_opps.views.sheetView[0].showGridLines = True

        opp_headers = [
            "Title", "Organization", "Category", "Description",
            "Required Skills", "Eligibility", "Country / Scope", "Remote Status",
            "Deadline", "Application URL", "Source URL", "Verification Status", "Score"
        ]

        for c_idx, h in enumerate(opp_headers, start=1):
            cell = ws_opps.cell(row=1, column=c_idx, value=h)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.border = self.thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for r_idx, opp in enumerate(new_opportunities, start=2):
            raw = opp.raw_data or {}
            skills = ", ".join(opp.tags) if opp.tags else (raw.get("required_skills") or "N/A")
            row_vals = [
                opp.title,
                opp.company or opp.provider or "N/A",
                (opp.category or "other").capitalize(),
                (opp.description or "")[:300],
                skills,
                opp.eligibility or raw.get("eligibility_criteria") or "All eligible applicants",
                opp.location or raw.get("country_or_scope") or "Global",
                "Remote" if opp.remote else "On-site / Regional",
                str(opp.deadline) if opp.deadline else "Open / Rolling",
                raw.get("application_url") or opp.url,
                opp.canonical_url or opp.url,
                "VERIFIED FREE",
                opp.score or 0,
            ]
            for c_idx, val in enumerate(row_vals, start=1):
                cell = ws_opps.cell(row=r_idx, column=c_idx, value=escape_formula_injection(val))
                cell.border = self.thin_border
                cell.font = Font(name="Calibri", size=10)
                if r_idx % 2 == 1:
                    cell.fill = self.row_alt_fill
                if c_idx in (8, 9, 12, 13):
                    cell.alignment = Alignment(horizontal="center", vertical="top")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=(c_idx in [4, 5]))

        # Auto-fit column widths
        col_widths = {
            1: 30, 2: 22, 3: 15, 4: 45, 5: 25, 6: 25,
            7: 18, 8: 14, 9: 15, 10: 35, 11: 35, 12: 18, 13: 10
        }
        for col_idx, width in col_widths.items():
            ws_opps.column_dimensions[get_column_letter(col_idx)].width = width

        # -------------------------------------------------------------
        # SHEET 3: Verification Details
        # -------------------------------------------------------------
        ws_verif = wb.create_sheet(title="Verification Details")
        ws_verif.views.sheetView[0].showGridLines = True

        verif_headers = [
            "Opportunity Title", "Decision", "Cost Status", "Compensation Status",
            "Pricing Evidence Excerpt", "Rule Triggered", "Approval Reason", "Verified At"
        ]

        for c_idx, h in enumerate(verif_headers, start=1):
            cell = ws_verif.cell(row=1, column=c_idx, value=h)
            cell.fill = self.sub_header_fill
            cell.font = self.header_font
            cell.border = self.thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for r_idx, v in enumerate(verification_details, start=2):
            v_vals = [
                v.get("title", ""),
                v.get("decision", "APPROVED"),
                v.get("participant_cost_status", "FREE"),
                v.get("participant_compensation_status", "N/A"),
                v.get("pricing_evidence_excerpt", "Corroborated free participation evidence in source."),
                v.get("rule_triggered", "RULE_APPROVE_VERIFIED_FREE_OPPORTUNITY"),
                v.get("reason", "Approved free-only opportunity."),
                v.get("verification_timestamp", date_str),
            ]
            for c_idx, val in enumerate(v_vals, start=1):
                cell = ws_verif.cell(row=r_idx, column=c_idx, value=escape_formula_injection(val))
                cell.border = self.thin_border
                cell.font = Font(name="Calibri", size=10)
                if r_idx % 2 == 1:
                    cell.fill = self.row_alt_fill
                if c_idx in (2, 3, 4, 8):
                    cell.alignment = Alignment(horizontal="center", vertical="top")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=(c_idx in [5, 7]))

        verif_col_widths = {
            1: 30, 2: 14, 3: 14, 4: 20, 5: 45, 6: 35, 7: 45, 8: 22
        }
        for col_idx, width in verif_col_widths.items():
            ws_verif.column_dimensions[get_column_letter(col_idx)].width = width

        # Save workbook
        wb.save(filepath)

        # Compute SHA-256 checksum
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        checksum = hasher.hexdigest()

        logger.info(f"Daily Excel report generated successfully: {filepath} (SHA-256: {checksum[:12]}...)")
        return filepath, checksum

