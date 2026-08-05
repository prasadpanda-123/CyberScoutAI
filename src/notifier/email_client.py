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

    def generate_summary_body(self, payload: Any, date_str: str) -> tuple[str, str]:
        """
        Generates text & HTML email report body including category summary breakdown
        and detailed opportunity list according to Phase 12.3 requirements.

        Returns:
            Tuple of (html_body, plain_text_body)
        """
        s = getattr(payload, "summary", payload)
        opportunities = getattr(payload, "all_opportunities", [])
        date_formatted = date_str.replace("_", "-")

        # Build Plaintext Summary & List
        plain_lines = [
            "Hello,\n",
            "CyberScout AI Daily Intelligence Report",
            f"Date: {date_formatted}\n",
            "===========================================================",
            "SUMMARY",
            "===========================================================",
            f"Total Opportunities : {getattr(s, 'total_opportunities', 0)}",
            f"Internships         : {getattr(s, 'internships', 0)}",
            f"Courses             : {getattr(s, 'courses', 0)}",
            f"Certifications      : {getattr(s, 'certifications', 0)}",
            f"Scholarships        : {getattr(s, 'scholarships', 0)}",
            f"Hackathons          : {getattr(s, 'hackathons', 0)}",
            f"CTFs                : {getattr(s, 'ctfs', 0)}",
            f"GitHub Repositories : {getattr(s, 'github_projects', 0)}",
            f"News                : {getattr(s, 'security_news', 0)}",
            f"Research            : {getattr(s, 'research', 0)}",
            f"Tools               : {getattr(s, 'tools', 0)}",
            "===========================================================\n",
        ]

        if opportunities:
            plain_lines.append("OPPORTUNITIES LIST")
            plain_lines.append("-----------------------------------------------------------")
            for idx, opp in enumerate(opportunities[:50], 1):
                company_str = opp.company or opp.provider or "N/A"
                loc_str = opp.location or ("Remote" if opp.remote else "Offline")
                mode_str = "Remote" if opp.remote else "Offline"
                deadline_str = str(opp.deadline) if opp.deadline else "N/A"
                conf_str = f"{getattr(opp, 'confidence_score', 0.0):.1f}/100"
                disc_str = str(opp.discovered_date) if opp.discovered_date else "N/A"

                plain_lines.append(f"{idx}. {opp.title}")
                plain_lines.append(f"   Organization : {company_str}")
                plain_lines.append(f"   Category     : {opp.category}")
                plain_lines.append(f"   Location     : {loc_str} ({mode_str})")
                plain_lines.append(f"   Deadline     : {deadline_str}")
                plain_lines.append(f"   Source       : {opp.source_id}")
                plain_lines.append(f"   Link         : {opp.url}")
                plain_lines.append(f"   Confidence   : {conf_str}")
                plain_lines.append(f"   Date         : {disc_str}")
                plain_lines.append("")

        plain_lines.append("Thank you.\nCyberScout AI\nNever Miss a Cybersecurity Opportunity Again.")
        plain_text = "\n".join(plain_lines)

        # Build HTML Summary & List
        opp_html_rows = []
        for opp in opportunities[:50]:
            company_str = opp.company or opp.provider or "N/A"
            loc_str = opp.location or ("Remote" if opp.remote else "Offline")
            mode_str = "Remote" if opp.remote else "Offline"
            deadline_str = str(opp.deadline) if opp.deadline else "N/A"
            conf_str = f"{getattr(opp, 'confidence_score', 0.0):.1f}"
            disc_str = str(opp.discovered_date) if opp.discovered_date else "N/A"

            opp_html_rows.append(f"""
            <tr style="border-bottom: 1px solid #E2E8F0;">
              <td style="padding: 10px 8px;">
                <a href="{opp.url}" target="_blank" style="color: #0284C7; font-weight: bold; text-decoration: none;">{opp.title}</a><br>
                <span style="font-size: 12px; color: #64748B;">{company_str} &bull; {opp.category}</span>
              </td>
              <td style="padding: 10px 8px; font-size: 13px;">{loc_str}<br><span style="font-size: 11px; color: #64748B;">{mode_str}</span></td>
              <td style="padding: 10px 8px; font-size: 13px;">{deadline_str}</td>
              <td style="padding: 10px 8px; font-size: 13px;">{opp.source_id}</td>
              <td style="padding: 10px 8px; font-size: 13px; font-weight: bold; color: #059669;">{conf_str}</td>
              <td style="padding: 10px 8px; font-size: 12px; color: #64748B;">{disc_str}</td>
            </tr>""")

        opp_table_html = f"""
        <h3 style="color: #0F172A; margin-top: 24px; margin-bottom: 12px;">Discovered Opportunities</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px; text-align: left;">
          <thead>
            <tr style="background-color: #F1F5F9; color: #334155; font-size: 12px; text-transform: uppercase;">
              <th style="padding: 8px;">Opportunity</th>
              <th style="padding: 8px;">Location</th>
              <th style="padding: 8px;">Deadline</th>
              <th style="padding: 8px;">Source</th>
              <th style="padding: 8px;">Confidence</th>
              <th style="padding: 8px;">Collected</th>
            </tr>
          </thead>
          <tbody>
            {''.join(opp_html_rows)}
          </tbody>
        </table>""" if opp_html_rows else ""

        html_text = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #1E293B; line-height: 1.5; padding: 20px; max-width: 800px; margin: 0 auto;">
  <div style="background-color: #0F172A; padding: 16px 24px; border-radius: 8px 8px 0 0; color: #FFFFFF;">
    <h2 style="margin: 0; font-size: 20px; color: #38BDF8;">CyberScout AI — Daily Intelligence Report</h2>
    <p style="margin: 4px 0 0 0; font-size: 13px; color: #94A3B8;">Date: {date_formatted}</p>
  </div>
  <div style="border: 1px solid #E2E8F0; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
    <h3 style="color: #0F172A; margin-top: 0; margin-bottom: 12px;">Summary Breakdown</h3>
    <table style="border-collapse: collapse; font-size: 14px; width: 100%; max-width: 400px; margin-bottom: 20px;">
      <tr><td style="padding: 4px 0;"><strong>Internships</strong></td><td style="text-align: right;">{getattr(s, 'internships', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>Courses</strong></td><td style="text-align: right;">{getattr(s, 'courses', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>Certifications</strong></td><td style="text-align: right;">{getattr(s, 'certifications', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>Scholarships</strong></td><td style="text-align: right;">{getattr(s, 'scholarships', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>Hackathons</strong></td><td style="text-align: right;">{getattr(s, 'hackathons', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>CTFs</strong></td><td style="text-align: right;">{getattr(s, 'ctfs', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>GitHub Repositories</strong></td><td style="text-align: right;">{getattr(s, 'github_projects', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>News</strong></td><td style="text-align: right;">{getattr(s, 'security_news', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>Research</strong></td><td style="text-align: right;">{getattr(s, 'research', 0)}</td></tr>
      <tr><td style="padding: 4px 0;"><strong>Tools</strong></td><td style="text-align: right;">{getattr(s, 'tools', 0)}</td></tr>
      <tr style="border-top: 2px solid #CBD5E1; font-weight: bold;"><td style="padding: 8px 0; font-size: 15px;">Total Opportunities</td><td style="text-align: right; color: #0284C7; font-size: 15px;">{getattr(s, 'total_opportunities', 0)}</td></tr>
    </table>

    {opp_table_html}

    <p style="margin-top: 24px; font-size: 13px; color: #64748B;">Please find the attached complete CSV & DOCX reports for details.</p>
    <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 20px 0;">
    <p style="margin: 0; font-size: 13px; color: #64748B;">
      <strong>CyberScout AI</strong> &bull; <em>Never Miss a Cybersecurity Opportunity Again.</em>
    </p>
  </div>
</body>
</html>"""

        return html_text, plain_text

    def send_daily_digest(self, send_empty: bool = False) -> Dict[str, Any]:
        """
        Retrieves active data, generates DOCX & CSV report files, and sends a summary email with attachments.
        Safely catches all configuration, database, and SMTP errors returning a JSON outcome dictionary.

        Args:
            send_empty: If True, dispatches an empty report email when no active opportunities exist.

        Returns:
            Outcome summary dictionary containing status and delivery logs.
        """
        try:
            # 1. Fetch active opportunities from database
            all_active = self.opp_repo.get_active_opportunities(limit=200)
            date_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")
            date_formatted = date_str.replace("_", "-")

            if not all_active:
                if send_empty:
                    subject = f"CyberScout AI Daily Intelligence Report - {date_formatted}"
                    plain_content = f"Hello,\n\nNo new cybersecurity opportunities were discovered today ({date_formatted}).\n\nCyberScout AI"
                    html_content = f"""<!DOCTYPE html><html><body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h3>CyberScout AI Daily Intelligence Report</h3>
                    <p>No new cybersecurity opportunities were discovered today ({date_formatted}).</p>
                    <p>Thank you.<br>CyberScout AI</p></body></html>"""
                    msg_id = self.smtp_sender.send_email(
                        html_content=html_content,
                        plain_content=plain_content,
                        subject=subject,
                        attachments=[],
                    )
                    return {"status": "success", "message": "Empty report email sent successfully.", "message_id": msg_id}
                return {"status": "skipped", "message": "No active opportunities found to send."}

            # 2. Generate DOCX & CSV report attachments via ReportManager
            report_res = self.report_manager.generate_reports(all_active, date_str=date_str)
            payload = self.report_manager.prepare_payload(all_active, date_str=date_str)

            if payload.summary.total_opportunities == 0:
                if send_empty:
                    subject = f"CyberScout AI Daily Intelligence Report - {date_formatted}"
                    plain_content = f"Hello,\n\nNo new cybersecurity opportunities were discovered today ({date_formatted}).\n\nCyberScout AI"
                    html_content = f"""<!DOCTYPE html><html><body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h3>CyberScout AI Daily Intelligence Report</h3>
                    <p>No new cybersecurity opportunities were discovered today ({date_formatted}).</p>
                    <p>Thank you.<br>CyberScout AI</p></body></html>"""
                    msg_id = self.smtp_sender.send_email(
                        html_content=html_content,
                        plain_content=plain_content,
                        subject=subject,
                        attachments=[],
                    )
                    return {"status": "success", "message": "Empty report email sent successfully.", "message_id": msg_id}
                return {"status": "skipped", "message": "No accepted opportunities found to send."}

            # 3. Render summary & opportunity list body
            render_start = time.time()
            html, text = self.generate_summary_body(payload, date_str=date_str)
            self.metrics.record_render(time.time() - render_start)

            # 4. Transmit email via SMTP with attachments
            send_start = time.time()
            subject = f"CyberScout AI Daily Intelligence Report - {date_formatted}"
            run_id = f"email-run-{int(time.time())}"

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
