"""
Notification Client Facade for CyberScout AI.

Generates DOCX/CSV report attachments and delivers a concise summary email.
"""

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any, Dict, Optional

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.notifier.history import HistoryTracker
from src.notifier.metrics import NotifierMetrics
from src.notifier.smtp_sender import SMTPSender
from src.reporting.report_manager import ReportManager


class EmailClient:
    """
    Unified manager client coordinating report generation, concise summary email rendering,
    and delivering email notifications with DOCX & CSV attachments.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        config_path: Optional[Path] = None,
        smtp_sender: Optional[SMTPSender] = None,
        history_tracker: Optional[HistoryTracker] = None,
        report_manager: Optional[ReportManager] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.config_path = config_path
        self.opp_repo = OpportunityRepository(db_manager=self.db_manager)
        self.smtp_sender = smtp_sender or SMTPSender(config_path=self.config_path)
        self.history_tracker = history_tracker or HistoryTracker(db_manager=self.db_manager)
        self.report_manager = report_manager or ReportManager()
        self.metrics = NotifierMetrics()

    def generate_summary_body(self, payload_summary: Any, date_str: str) -> tuple[str, str]:
        """
        Generates short text & HTML summary bodies (< 25 lines).

        Returns:
            Tuple of (html_body, plain_text_body)
        """
        s = payload_summary
        date_formatted = date_str.replace("_", "-")

        plain_text = (
            "Hello,\n\n"
            "CyberScout AI has completed today's intelligence scan.\n\n"
            "Summary\n\n"
            f"Internships      : {s.internships}\n"
            f"Courses          : {s.courses}\n"
            f"Certifications   : {s.certifications}\n"
            f"Hackathons       : {s.hackathons}\n"
            f"CTFs             : {s.ctfs}\n"
            f"Scholarships     : {s.scholarships}\n"
            f"Research         : {s.research}\n"
            f"Security News    : {s.security_news}\n"
            f"GitHub Projects  : {s.github_projects}\n\n"
            f"Total Opportunities : {s.total_opportunities}\n\n"
            "Please find the complete report attached.\n\n"
            "Attachments\n"
            f"✔ CyberScout_Report_{date_str}.docx\n"
            f"✔ CyberScout_Report_{date_str}.csv\n\n"
            "Thank you.\n\n"
            "CyberScout AI\n"
            "Never Miss a Cybersecurity Opportunity Again."
        )

        html_text = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #1E293B; line-height: 1.5; padding: 20px;">
  <p>Hello,</p>
  <p>CyberScout AI has completed today's intelligence scan.</p>
  <h3 style="color: #0F172A; margin-bottom: 8px;">Summary</h3>
  <table style="border-collapse: collapse; font-size: 14px; width: 320px; margin-bottom: 16px;">
    <tr><td style="padding: 3px 0;"><strong>Internships</strong></td><td style="text-align: right;">{s.internships}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>Courses</strong></td><td style="text-align: right;">{s.courses}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>Certifications</strong></td><td style="text-align: right;">{s.certifications}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>Hackathons</strong></td><td style="text-align: right;">{s.hackathons}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>CTFs</strong></td><td style="text-align: right;">{s.ctfs}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>Scholarships</strong></td><td style="text-align: right;">{s.scholarships}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>Research</strong></td><td style="text-align: right;">{s.research}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>Security News</strong></td><td style="text-align: right;">{s.security_news}</td></tr>
    <tr><td style="padding: 3px 0;"><strong>GitHub Projects</strong></td><td style="text-align: right;">{s.github_projects}</td></tr>
    <tr style="border-top: 1px solid #CBD5E1; font-weight: bold;"><td style="padding: 6px 0;">Total Opportunities</td><td style="text-align: right; color: #0EA5E9;">{s.total_opportunities}</td></tr>
  </table>
  <p>Please find the complete report attached.</p>
  <p><strong>Attachments</strong><br>
  ✔ CyberScout_Report_{date_str}.docx<br>
  ✔ CyberScout_Report_{date_str}.csv</p>
  <p>Thank you.<br><br>
  <strong>CyberScout AI</strong><br>
  <em>Never Miss a Cybersecurity Opportunity Again.</em></p>
</body>
</html>"""

        return html_text, plain_text

    def send_daily_digest(self) -> Dict[str, Any]:
        """
        Retrieves active data, generates DOCX & CSV report files, and sends a summary email with attachments.

        Returns:
            Outcome summary dictionary containing status and delivery logs.
        """
        # 1. Fetch active opportunities from database
        all_active = self.opp_repo.get_active_opportunities(limit=200)
        if not all_active:
            return {"status": "skipped", "message": "No active opportunities found to send."}

        date_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")

        # 2. Generate DOCX & CSV report attachments via ReportManager
        report_res = self.report_manager.generate_reports(all_active, date_str=date_str)
        payload = self.report_manager.prepare_payload(all_active, date_str=date_str)

        if payload.summary.total_opportunities == 0:
            return {"status": "skipped", "message": "No accepted opportunities found to send."}

        # 3. Render concise summary body
        render_start = time.time()
        html, text = self.generate_summary_body(payload.summary, date_str=date_str)
        self.metrics.record_render(time.time() - render_start)

        # 4. Transmit email via SMTP with attachments
        send_start = time.time()
        subject = f"CyberScout AI Daily Intelligence Report - {date_str.replace('_', '-')}"
        run_id = f"email-run-{int(time.time())}"

        try:
            msg_id = self.smtp_sender.send_email(
                html_content=html,
                plain_content=text,
                subject=subject,
                attachments=report_res.attachment_paths,
            )
            send_duration = time.time() - send_start
            self.metrics.record_sent(send_duration)

            # Record delivery history for sent opportunities
            for opp in payload.all_opportunities:
                self.history_tracker.log_delivery(opp.id, email_run_id=run_id)

            return {
                "status": "success",
                "message_id": msg_id,
                "opportunities_sent": payload.summary.total_opportunities,
                "attachments_sent": [p.name for p in report_res.attachment_paths],
                "report_generation_time_sec": report_res.generation_time_sec,
                "metrics": self.metrics.get_summary(),
            }

        except Exception as e:
            self.metrics.record_failed()
            return {
                "status": "failed",
                "error": str(e),
                "metrics": self.metrics.get_summary(),
            }
