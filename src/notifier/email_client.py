"""
Notification Client Facade for CyberScout AI.

Generates report files and delivers a scan-scoped summary with a single CSV attachment via Brevo API.
"""

from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.notifier.email_sender import EmailSender
from src.notifier.history import HistoryTracker
from src.notifier.metrics import NotifierMetrics
from src.reporting.report_manager import ReportManager


class EmailClient:
    """
    Unified manager client coordinating report generation, concise summary rendering,
    and delivering scan-scoped email notifications with one CSV attachment.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        config_path: Optional[Path] = None,
        email_sender: Optional[EmailSender] = None,
        history_tracker: Optional[HistoryTracker] = None,
        report_manager: Optional[ReportManager] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.config_path = config_path
        self.opp_repo = OpportunityRepository(db_manager=self.db_manager)
        self.email_sender = email_sender or EmailSender(config_path=self.config_path)
        # Backward compatibility alias
        self.smtp_sender = self.email_sender
        self.history_tracker = history_tracker or HistoryTracker(db_manager=self.db_manager)
        self.report_manager = report_manager or ReportManager()
        self.metrics = NotifierMetrics()

    def check_smtp_connectivity(self) -> Dict[str, Any]:
        """
        Executes pre-flight HTTPS API authentication & connectivity check against Brevo REST API.
        """
        return self.email_sender.check_health()

    def generate_summary_body(self, payload: Any, date_str: str) -> tuple[str, str]:
        """Render a clean, email-client-friendly report for the current scan."""
        summary = getattr(payload, "summary", payload)
        opportunities = getattr(payload, "all_opportunities", [])
        date_formatted = date_str.replace("_", "-")
        total = getattr(summary, "total_opportunities", 0)

        category_rows = [
            ("Internships", "internships"),
            ("Courses", "courses"),
            ("Certifications", "certifications"),
            ("Scholarships", "scholarships"),
            ("Hackathons", "hackathons"),
            ("CTFs", "ctfs"),
            ("GitHub Repositories", "github_projects"),
            ("News", "security_news"),
            ("Research", "research"),
            ("Tools", "tools"),
        ]

        plain_lines = [
            "CyberScout AI Daily Intelligence Report",
            f"Scan date: {date_formatted}",
            f"{total} new or changed opportunities in this scan.",
            "",
            "SUMMARY BREAKDOWN",
        ]
        for label, attr in category_rows:
            plain_lines.append(f"{label}: {getattr(summary, attr, 0)}")

        esc = lambda value: html_escape(str(value or ""), quote=True)
        category_html_rows = []
        for index in range(0, len(category_rows), 2):
            left_label, left_attr = category_rows[index]
            right_label, right_attr = category_rows[index + 1]
            category_html_rows.append(f"""
              <tr>
                <td style="width:50%;padding:9px 12px;border-bottom:1px solid #e8edf3;color:#526174;">{left_label}</td>
                <td style="width:50%;padding:9px 12px;border-bottom:1px solid #e8edf3;text-align:right;font-weight:700;color:#172b4d;">{getattr(summary, left_attr, 0)}</td>
              </tr>
              <tr>
                <td style="padding:9px 12px;border-bottom:1px solid #e8edf3;color:#526174;">{right_label}</td>
                <td style="padding:9px 12px;border-bottom:1px solid #e8edf3;text-align:right;font-weight:700;color:#172b4d;">{getattr(summary, right_attr, 0)}</td>
              </tr>""")

        opportunity_rows = []
        if opportunities:
            plain_lines.extend(["", "OPPORTUNITIES FROM THIS SCAN"])
        for index, opportunity in enumerate(opportunities[:50], 1):
            organization = opportunity.company or opportunity.provider or "N/A"
            location = opportunity.location or ("Remote" if opportunity.remote else "On-site")
            deadline = opportunity.deadline or "Open / rolling"
            source_name = opportunity.source_id or "N/A"
            confidence = getattr(opportunity, "confidence_score", 0.0) or 0.0
            raw_url = str(opportunity.url or "")
            safe_url = html_escape(raw_url, quote=True)
            title = esc(opportunity.title or "Untitled opportunity")
            title_html = (
                f'<a href="{safe_url}" style="color:#087eaa;text-decoration:none;font-weight:700;">{title}</a>'
                if raw_url.lower().startswith(("https://", "http://"))
                else title
            )
            plain_lines.extend([
                "",
                f"{index}. {opportunity.title}",
                f"   {organization} | {opportunity.category} | {location}",
                f"   Deadline: {deadline}",
                f"   Source: {source_name}",
                f"   Confidence: {confidence:.1f}/100",
                f"   Apply: {raw_url}",
            ])
            opportunity_rows.append(f"""
              <tr>
                <td style="padding:13px 12px;border-bottom:1px solid #e8edf3;vertical-align:top;">{title_html}<br>
                  <span style="font-size:12px;color:#718096;">{esc(organization)} &middot; {esc(opportunity.category)}</span></td>
                <td style="padding:13px 10px;border-bottom:1px solid #e8edf3;vertical-align:top;color:#526174;">{esc(location)}</td>
                <td style="padding:13px 10px;border-bottom:1px solid #e8edf3;vertical-align:top;color:#526174;">{esc(deadline)}</td>
                <td style="padding:13px 10px;border-bottom:1px solid #e8edf3;vertical-align:top;color:#526174;">{esc(source_name)}</td>
                <td style="padding:13px 10px;border-bottom:1px solid #e8edf3;vertical-align:top;text-align:right;color:#07866f;font-weight:700;">{confidence:.1f}</td>
              </tr>""")

        plain_lines.extend(["", "CyberScout AI | Never Miss a Cybersecurity Opportunity Again."])
        plain_text = "\n".join(plain_lines)

        if opportunity_rows:
            opportunity_section = f"""
          <h2 style="margin:28px 0 12px;color:#172b4d;font-size:17px;">Opportunities from this scan</h2>
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;font-size:13px;">
            <thead><tr style="background:#f2f6fa;color:#526174;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.04em;">
              <th style="padding:10px 12px;">Opportunity</th><th style="padding:10px;">Location</th><th style="padding:10px;">Deadline</th><th style="padding:10px;">Source</th><th style="padding:10px;text-align:right;">Confidence</th>
            </tr></thead><tbody>{''.join(opportunity_rows)}</tbody>
          </table>"""
        else:
            opportunity_section = """
          <div style="margin-top:24px;padding:18px;background:#f5f8fb;border:1px solid #e8edf3;border-radius:6px;color:#526174;">
            No new or updated opportunities were found in this scan.
          </div>"""

        html_text = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:24px 12px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#243247;line-height:1.5;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:760px;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <tr><td style="padding:25px 30px;background:#10233f;border-bottom:4px solid #12a6c7;">
        <div style="font-size:11px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:#75d5e7;">CyberScout AI &nbsp; / &nbsp; Scan report</div>
        <h1 style="margin:8px 0 2px;font-size:23px;line-height:1.3;color:#ffffff;">Daily Intelligence Report</h1>
        <p style="margin:4px 0 0;color:#c5d2e2;font-size:13px;">{date_formatted} &nbsp;&middot;&nbsp; {total} new or changed opportunities</p>
      </td></tr>
      <tr><td style="padding:24px 30px 8px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:20px;background:#f2f8fb;border:1px solid #dcebf1;border-radius:6px;">
          <tr><td style="padding:16px 18px;width:25%;border-right:1px solid #dcebf1;">
            <div style="font-size:26px;font-weight:700;color:#087eaa;">{total}</div><div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#65758b;">In this scan</div>
          </td><td style="padding:16px 18px;">
            <div style="font-size:15px;font-weight:700;color:#172b4d;">Fresh scan results</div><div style="font-size:12px;color:#65758b;">This report contains only opportunities found or changed in this scan.</div>
          </td></tr>
        </table>
        <h2 style="margin:0 0 10px;color:#172b4d;font-size:17px;">Summary breakdown</h2>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border:1px solid #e8edf3;border-collapse:collapse;font-size:13px;">
          {''.join(category_html_rows)}
          <tr style="background:#f7f9fb;"><td style="padding:11px 12px;font-weight:700;color:#172b4d;">Total opportunities</td><td style="padding:11px 12px;text-align:right;font-size:15px;font-weight:700;color:#087eaa;">{total}</td></tr>
        </table>
        {opportunity_section}
        <p style="margin:20px 0 0;padding:13px 15px;background:#f7f9fb;border-left:3px solid #12a6c7;color:#526174;font-size:12px;">The attached CSV contains the same new and changed opportunities shown in this report.</p>
      </td></tr>
      <tr><td style="padding:17px 30px;border-top:1px solid #e8edf3;color:#718096;font-size:12px;">
        <strong style="color:#526174;">CyberScout AI</strong> &nbsp;&middot;&nbsp; Never Miss a Cybersecurity Opportunity Again.
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""
        return html_text, plain_text


    def send_daily_digest(
        self,
        send_empty: bool = False,
        scan_opportunities: Optional[List[Any]] = None,
        scan_opportunity_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send a fresh CSV digest. Scan-scoped inputs prevent older active records
        from leaking into email sent after a scan.
        """
        try:
            if scan_opportunities is not None:
                opportunities = list(scan_opportunities)
            elif scan_opportunity_ids is not None:
                opportunities = [
                    opportunity
                    for opportunity_id in dict.fromkeys(scan_opportunity_ids)
                    if (opportunity := self.opp_repo.get_by_id(opportunity_id)) is not None
                ]
            else:
                # Keep the manual digest command compatible when no scan context exists.
                opportunities = self.opp_repo.get_active_opportunities(limit=200)

            date_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")
            date_formatted = date_str.replace("_", "-")
            payload = self.report_manager.prepare_payload(opportunities, date_str=date_str)

            if payload.summary.total_opportunities == 0:
                if not send_empty:
                    return {"status": "skipped", "message": "No new or updated opportunities found in this scan."}

                html_content, plain_content = self.generate_summary_body(payload, date_str=date_str)
                subject = f"CyberScout AI Daily Intelligence Report - {date_formatted} [No New Opportunities]"
                msg_id = self.email_sender.send_email(
                    html_content=html_content,
                    plain_content=plain_content,
                    subject=subject,
                    attachments=[],
                )
                return {
                    "status": "success",
                    "message": "Empty report email sent successfully.",
                    "message_id": msg_id,
                    "attachments_sent": [],
                }

            # Generate this run's reports from only the supplied scan results.
            report_res = self.report_manager.generate_reports(
                payload.all_opportunities,
                date_str=date_str,
            )
            if not report_res.csv_path or not report_res.csv_path.is_file():
                raise RuntimeError("Fresh CSV report generation failed; refusing to send an outdated or incomplete attachment.")

            render_start = time.time()
            html, text = self.generate_summary_body(payload, date_str=date_str)
            self.metrics.record_render(time.time() - render_start)

            send_start = time.time()
            subject = f"CyberScout AI Daily Intelligence Report - {date_formatted} ({payload.summary.total_opportunities} New or Changed)"
            run_id = f"email-run-{int(time.time())}"
            email_attachments = [report_res.csv_path]

            msg_id = self.email_sender.send_email(
                html_content=html,
                plain_content=text,
                subject=subject,
                attachments=email_attachments,
            )
            self.metrics.record_sent(time.time() - send_start)

            opp_ids = [opp.id for opp in payload.all_opportunities if getattr(opp, "id", None)]
            if opp_ids:
                self.history_tracker.log_deliveries_batch(opp_ids, email_run_id=run_id)

            return {
                "status": "success",
                "message_id": msg_id,
                "opportunities_sent": payload.summary.total_opportunities,
                "attachments_sent": [path.name for path in email_attachments],
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
