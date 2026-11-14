"""
Notification Delivery Service for CyberScout AI (Phase F).

Manages daily intelligence report notifications via Brevo API, enforcing strict
database-level delivery idempotency, single Excel attachment delivery, professional
HTML rendering, and concise status-only messaging when no new opportunities exist.
"""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import zoneinfo

from src.core.logging import get_logger
from src.discovery.daily_excel_report import DailyExcelReportGenerator
from src.discovery.promotion_models import DailyReportMetadata, EmailDeliveryRecord
from src.discovery.promotion_repository import PromotionRepository
from src.models.opportunity import Opportunity
from src.notifier.email_sender import EmailSender

logger = get_logger(__name__)


class NotificationDeliveryService:
    """
    Coordinates daily intelligence digest distribution via Brevo API
    with strict idempotency tracking in PostgreSQL.
    """

    def __init__(
        self,
        repository: Optional[PromotionRepository] = None,
        email_sender: Optional[EmailSender] = None,
        report_generator: Optional[DailyExcelReportGenerator] = None,
        delivery_enabled: Optional[bool] = None,
        default_recipient: Optional[str] = None,
        timezone_name: str = "Asia/Kolkata",
    ):
        self.repository = repository or PromotionRepository()
        self.email_sender = email_sender or EmailSender()
        self.report_generator = report_generator or DailyExcelReportGenerator()

        # Load environment settings with safe conservative defaults
        env_enabled = os.getenv("EMAIL_DELIVERY_ENABLED")
        if delivery_enabled is not None:
            self.delivery_enabled = delivery_enabled
        elif env_enabled is not None:
            self.delivery_enabled = env_enabled.strip().lower() in ("true", "1", "yes")
        else:
            self.delivery_enabled = False

        self.recipient = (
            default_recipient
            or os.getenv("DAILY_REPORT_RECIPIENT")
            or os.getenv("ADMIN_EMAIL")
            or os.getenv("REPORT_RECIPIENT")
            or "alerts@cyberscout.ai"
        ).strip()

        self.timezone_name = os.getenv("DAILY_REPORT_TIMEZONE") or timezone_name or "Asia/Kolkata"
        try:
            self.tz = zoneinfo.ZoneInfo(self.timezone_name)
        except Exception:
            self.tz = timezone.utc

    def get_today_date_str(self) -> str:
        """Returns current YYYY-MM-DD date string in configured timezone."""
        return datetime.now(self.tz).strftime("%Y-%m-%d")

    def render_daily_html(
        self,
        report_date: str,
        metadata: DailyReportMetadata,
        new_opportunities: List[Opportunity],
        attachment_filename: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Renders responsive professional HTML email and fallback plaintext content.
        """
        has_new = len(new_opportunities) > 0

        # Plaintext Fallback
        plain_lines = [
            "===========================================================",
            f"CYBERSCOUT AI — DAILY INTELLIGENCE REPORT ({report_date})",
            "===========================================================",
            f"Report Date : {report_date} ({self.timezone_name})",
            f"Status      : {'New Opportunities Found' if has_new else 'No New Opportunities Today'}",
            "-----------------------------------------------------------",
            "PIPELINE METRICS:",
            f"- Discovered Candidates   : {metadata.total_discovered}",
            f"- Extracted Pages         : {metadata.total_extracted}",
            f"- AI Classified           : {metadata.total_classified}",
            f"- Free-Only Approved      : {metadata.total_approved}",
            f"- Rejected / Quarantined  : {metadata.total_rejected} / {metadata.total_quarantined}",
            f"- Newly Promoted to Prod  : {metadata.newly_promoted_count}",
            f"- Total Active Knowledge  : {metadata.total_active_production}",
            "===========================================================",
        ]

        if has_new:
            plain_lines.append("\nNEW OPPORTUNITY HIGHLIGHTS:")
            for idx, opp in enumerate(new_opportunities[:10], start=1):
                loc = opp.location or ("Remote" if opp.remote else "On-site")
                plain_lines.append(f"{idx}. {opp.title} ({opp.company or opp.provider or 'N/A'})")
                plain_lines.append(f"   Category: {opp.category} | Location: {loc} | Deadline: {opp.deadline or 'Rolling'}")
                plain_lines.append(f"   Apply: {opp.url}\n")
            if attachment_filename:
                plain_lines.append(f"\nFull details and verification audit trail attached: {attachment_filename}")
        else:
            plain_lines.append("\nNo new cybersecurity opportunities were discovered today.")
            plain_lines.append("Existing opportunities remain monitored for deadline updates.")

        plain_text = "\n".join(plain_lines)

        # HTML Rendering
        cards_html = ""
        if has_new:
            for opp in new_opportunities[:10]:
                org = opp.company or opp.provider or "N/A"
                loc = opp.location or ("Remote" if opp.remote else "On-site")
                skills = ", ".join(opp.tags[:4]) if opp.tags else "Cybersecurity"
                cards_html += f"""
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                  <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                      <span style="display: inline-block; background: #ebf8ff; color: #2b6cb0; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase;">
                        {opp.category}
                      </span>
                      <span style="display: inline-block; background: #f0fff4; color: #276749; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-left: 6px;">
                        VERIFIED FREE
                      </span>
                      <h4 style="margin: 8px 0 4px 0; color: #1a202c; font-size: 16px;">{opp.title}</h4>
                      <p style="margin: 0 0 8px 0; color: #4a5568; font-size: 13px;"><strong>{org}</strong> • {loc} • Deadline: <strong>{opp.deadline or 'Open / Rolling'}</strong></p>
                    </div>
                    <div style="text-align: right;">
                      <span style="background: #edf2f7; color: #2d3748; font-size: 12px; font-weight: bold; padding: 4px 8px; border-radius: 6px;">
                        Score: {opp.score}
                      </span>
                    </div>
                  </div>
                  <p style="margin: 0 0 12px 0; color: #718096; font-size: 13px; line-height: 1.4;">
                    {(opp.description or '')[:180]}...
                  </p>
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #718096; font-size: 11px;">Skills: {skills}</span>
                    <a href="{opp.url}" style="background: #3182ce; color: #ffffff; text-decoration: none; padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: bold;" target="_blank">
                      View & Apply →
                    </a>
                  </div>
                </div>
                """

        html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CyberScout AI Daily Report</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f7fafc; margin: 0; padding: 24px; color: #2d3748;">
  <div style="max-width: 680px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
    
    <!-- Header Banner -->
    <div style="background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%); color: #ffffff; padding: 28px 32px;">
      <h2 style="margin: 0 0 6px 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px;">CyberScout AI</h2>
      <p style="margin: 0; font-size: 14px; color: #bee3f8;">
        Daily Opportunity Intelligence Digest • <strong>{report_date}</strong>
      </p>
    </div>

    <!-- Summary Metrics Grid -->
    <div style="padding: 24px 32px 16px 32px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
      <h3 style="margin: 0 0 14px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: #4a5568;">Pipeline Execution Summary</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 8px 12px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center; width: 33%;">
            <div style="font-size: 20px; font-weight: bold; color: #2b6cb0;">{metadata.total_discovered}</div>
            <div style="font-size: 11px; color: #718096; text-transform: uppercase;">Discovered</div>
          </td>
          <td style="padding: 8px 12px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center; width: 33%;">
            <div style="font-size: 20px; font-weight: bold; color: #38a169;">{metadata.total_approved}</div>
            <div style="font-size: 11px; color: #718096; text-transform: uppercase;">Approved Free</div>
          </td>
          <td style="padding: 8px 12px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; text-align: center; width: 33%;">
            <div style="font-size: 20px; font-weight: bold; color: #3182ce;">{metadata.newly_promoted_count}</div>
            <div style="font-size: 11px; color: #718096; text-transform: uppercase;">Newly Published</div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Main Content Area -->
    <div style="padding: 24px 32px;">
      {'<h3 style="margin: 0 0 16px 0; font-size: 16px; color: #1a202c;">Top Promoted Opportunities Today</h3>' if has_new else ''}
      {cards_html if has_new else '<div style="text-align: center; padding: 32px 16px;"><p style="font-size: 15px; color: #4a5568; margin-bottom: 8px;">No new cybersecurity opportunities were discovered today (' + report_date + ').</p><p style="font-size: 13px; color: #718096; margin: 0;">Our global discovery engine continuously monitors security sources, platforms, and institutions.</p></div>'}
    </div>

    <!-- Attachment & Footer Banner -->
    <div style="background: #f8fafc; padding: 20px 32px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #718096;">
      {f'<p style="margin: 0 0 10px 0;"><strong>Attached Workbook:</strong> <span style="color: #2b6cb0;">{attachment_filename}</span> (includes full verification breakdown & audit trail).</p>' if (has_new and attachment_filename) else ''}
      <p style="margin: 0; line-height: 1.5;">
        Delivered automatically by <strong>CyberScout AI</strong> — Deterministic Zero-Cost Cybersecurity Intelligence.<br>
        All published opportunities have been strictly verified to be free to participate or apply.
      </p>
    </div>

  </div>
</body>
</html>"""

        return html_text, plain_text

    def deliver_daily_report(
        self,
        report_date: Optional[str] = None,
        metadata: Optional[DailyReportMetadata] = None,
        new_opportunities: Optional[List[Opportunity]] = None,
        verification_details: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes daily report delivery with database idempotency protection.

        Sequence:
        1. Checks whether report for (report_date, recipient) has already been sent.
        2. Generates Excel workbook if new opportunities exist.
        3. Renders HTML digest.
        4. Transmits email via Brevo REST API.
        5. Updates database delivery status atomically.

        Returns:
            Dict detailing delivery status and provider response.
        """
        date_str = report_date or self.get_today_date_str()
        recipient = self.recipient
        report_id = f"daily_report_{date_str}_{recipient.replace('@', '_at_')}"

        logger.info(
            f"[NotificationDelivery] Evaluating delivery for {date_str} to {recipient} "
            f"(delivery_enabled={self.delivery_enabled}, dry_run={dry_run})."
        )

        # 1. Database-Level Idempotency Check
        existing_record = self.repository.get_delivery_record(date_str, recipient)
        if existing_record and existing_record.delivery_status == "sent":
            logger.info(
                f"[NotificationDelivery] Daily report '{report_id}' has already been delivered "
                f"successfully (Message ID: {existing_record.provider_message_id}). Skipping."
            )
            return {
                "status": "skipped",
                "reason": "Already delivered for today",
                "report_identifier": report_id,
                "provider_message_id": existing_record.provider_message_id,
            }

        # 2. Gather Data and Compile Excel Workbook (if new opportunities exist)
        meta = metadata or self.repository.get_daily_summary_counts(date_str)
        opps = new_opportunities or []
        verifs = verification_details or []

        attachment_path: Optional[Path] = None
        attachment_checksum: Optional[str] = None
        attachments_to_send: List[Path] = []

        if len(opps) > 0:
            excel_path, checksum = self.report_generator.generate_report(
                metadata=meta,
                new_opportunities=opps,
                verification_details=verifs,
                report_date_str=date_str,
            )
            attachment_path = excel_path
            attachment_checksum = checksum
            attachments_to_send = [excel_path]
        else:
            logger.info("[NotificationDelivery] No new opportunities today: generating status-only email without attachment.")

        # 3. Render HTML and Plaintext Content
        attachment_name = attachment_path.name if attachment_path else None
        html_body, text_body = self.render_daily_html(
            report_date=date_str,
            metadata=meta,
            new_opportunities=opps,
            attachment_filename=attachment_name,
        )

        subject = (
            f"CyberScout AI Daily Intelligence Report - {date_str} "
            f"({len(opps)} New Opportunities)" if len(opps) > 0
            else f"CyberScout AI Daily Intelligence Report - {date_str} [No New Opportunities]"
        )

        # 4. Record Initial Pending Attempt
        delivery_rec = EmailDeliveryRecord(
            report_date=date_str,
            recipient=recipient,
            report_identifier=report_id,
            opportunity_ids=[o.id for o in opps if getattr(o, "id", None)],
            attachment_path=str(attachment_path) if attachment_path else None,
            attachment_checksum=attachment_checksum,
            delivery_status="pending",
        )
        if not dry_run:
            try:
                self.repository.record_delivery_attempt(delivery_rec)
            except Exception as rec_err:
                logger.warning(f"Could not record delivery attempt: {rec_err}")

        # 5. Check if Delivery is Enabled or Dry-Run
        if dry_run or not self.delivery_enabled:
            logger.info(
                f"[NotificationDelivery] Skipping email transmission (dry_run={dry_run}, "
                f"delivery_enabled={self.delivery_enabled})."
            )
            return {
                "status": "dry_run",
                "report_identifier": report_id,
                "opportunities_count": len(opps),
                "attachment": str(attachment_path) if attachment_path else None,
                "attachment_checksum": attachment_checksum,
                "subject": subject,
            }

        # 6. Transmit Email via Brevo REST API
        try:
            msg_id = self.email_sender.send_email(
                html_content=html_body,
                plain_content=text_body,
                subject=subject,
                recipient=recipient,
                attachments=attachments_to_send,
            )
            logger.info(f"[NotificationDelivery] Daily email report sent successfully to {recipient} (MsgID: {msg_id}).")
            self.repository.update_delivery_success(report_id, msg_id)
            return {
                "status": "success",
                "message_id": msg_id,
                "report_identifier": report_id,
                "opportunities_sent": len(opps),
                "attachment_sent": attachment_name,
            }
        except Exception as send_err:
            error_str = str(send_err)
            logger.error(f"[NotificationDelivery] Failed to send daily email: {error_str}")
            self.repository.update_delivery_failure(report_id, error_str)
            return {
                "status": "failed",
                "error": error_str,
                "report_identifier": report_id,
            }
