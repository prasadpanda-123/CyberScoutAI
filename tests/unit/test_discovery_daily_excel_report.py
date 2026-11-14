"""
Unit Tests for Phase F Daily Excel Report Generator.
"""

from pathlib import Path
import tempfile
import openpyxl
import pytest

from src.discovery.daily_excel_report import DailyExcelReportGenerator, escape_formula_injection
from src.discovery.promotion_models import DailyReportMetadata
from src.models.opportunity import Opportunity


class TestDailyExcelReport:
    """Test suite for daily Excel workbook generation and security controls."""

    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.generator = DailyExcelReportGenerator(output_dir=self.output_dir)

    def teardown_method(self):
        self.temp_dir.cleanup()

    def test_formula_injection_sanitization(self):
        """Verifies formulas starting with =, +, -, @ are safely escaped."""
        assert escape_formula_injection("=SUM(A1:A10)") == "'=SUM(A1:A10)"
        assert escape_formula_injection("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
        assert escape_formula_injection("-100") == "'-100"
        assert escape_formula_injection("@SUM(B2)") == "'@SUM(B2)"
        assert escape_formula_injection("Normal Text") == "Normal Text"
        assert escape_formula_injection(42) == 42

    def test_workbook_structure_and_sheets(self):
        """Verifies exactly 3 structured sheets are created with correct headers."""
        meta = DailyReportMetadata(
            report_date="2026-11-13",
            timezone="Asia/Kolkata",
            total_discovered=50,
            total_extracted=48,
            total_classified=45,
            total_approved=20,
            total_rejected=15,
            total_quarantined=10,
            newly_promoted_count=5,
            existing_updated_count=2,
            total_active_production=125,
        )

        sample_opp = Opportunity(
            id="test-opp-1",
            title="=HYPERLINK(\"http://evil.com\", \"Click Me\")", # Malicious formula attempt
            url="https://cyber.example.com/apply",
            source_id="tavily",
            company="GovSec India",
            category="internship",
            description="Summer cybersecurity internship.",
            location="India",
            remote=True,
            deadline="2026-05-30",
            score=88,
            tags=["Python", "SOC"],
        )

        verif_data = [{
            "title": sample_opp.title,
            "decision": "APPROVED",
            "participant_cost_status": "FREE",
            "participant_compensation_status": "PAID",
            "pricing_evidence_excerpt": "Selected interns receive stipend. No application fee.",
            "rule_triggered": "RULE_APPROVE_COMPENSATED_EMPLOYMENT_WITHOUT_FEE",
            "reason": "Approved free-only opportunity.",
            "verification_timestamp": "2026-11-13T10:00:00Z",
        }]

        filepath, checksum = self.generator.generate_report(
            metadata=meta,
            new_opportunities=[sample_opp],
            verification_details=verif_data,
            report_date_str="2026-11-13",
        )

        assert filepath.exists()
        assert len(checksum) == 64 # Valid SHA-256

        # Inspect workbook
        wb = openpyxl.load_workbook(filepath)
        sheet_names = wb.sheetnames
        assert sheet_names == ["Daily Summary", "New Opportunities", "Verification Details"]

        # Check Sheet 1 (Daily Summary)
        ws_summary = wb["Daily Summary"]
        assert ws_summary["A1"].value == "CyberScout AI — Daily Opportunity Discovery Summary"
        assert ws_summary["B5"].value == "2026-11-13" # Report Date
        assert ws_summary["B6"].value == 50 # Discovered
        assert ws_summary["B9"].value == 20 # Approved

        # Check Sheet 2 (New Opportunities)
        ws_opps = wb["New Opportunities"]
        assert ws_opps["A1"].value == "Title"
        # Verify formula was sanitized!
        title_cell_value = ws_opps["A2"].value
        assert title_cell_value.startswith("'="), "Formula injection must be prepended with single quote"

        # Check Sheet 3 (Verification Details)
        ws_verif = wb["Verification Details"]
        assert ws_verif["A1"].value == "Opportunity Title"
        assert ws_verif["B2"].value == "APPROVED"
        assert ws_verif["C2"].value == "FREE"

    def test_empty_opportunities_report(self):
        """Verifies report generation when 0 new opportunities exist."""
        meta = DailyReportMetadata(
            report_date="2026-11-13",
            newly_promoted_count=0,
            total_active_production=100,
        )

        filepath, checksum = self.generator.generate_report(
            metadata=meta,
            new_opportunities=[],
            verification_details=[],
            report_date_str="2026-11-13",
        )

        assert filepath.exists()
        wb = openpyxl.load_workbook(filepath)
        ws_opps = wb["New Opportunities"]
        assert ws_opps.max_row == 1 # Only header row

