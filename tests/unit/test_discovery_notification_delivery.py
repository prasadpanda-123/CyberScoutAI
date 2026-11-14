"""
Unit Tests for Phase F Notification Delivery Service & Idempotency Engine.
"""

from pathlib import Path
import tempfile
import pytest

from src.discovery.notification_delivery_service import NotificationDeliveryService
from src.discovery.promotion_models import DailyReportMetadata, EmailDeliveryRecord
from src.models.opportunity import Opportunity


class MockEmailSender:
    """Mock EmailSender recording send calls without external network access."""

    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.sent_emails = []

    def send_email(self, html_content, plain_content, subject, recipient=None, attachments=None):
        if self.should_fail:
            from src.notifier.exceptions import NotificationError
            raise NotificationError("[MAIL_SEND] Brevo API rate limit exceeded")
        msg_id = f"brevo-mock-{len(self.sent_emails) + 1}"
        self.sent_emails.append({
            "html": html_content,
            "plain": plain_content,
            "subject": subject,
            "recipient": recipient,
            "attachments": attachments or [],
            "message_id": msg_id,
        })
        return msg_id


class MockDeliveryRepository:
    """Mock repository tracking delivery records for unit testing idempotency."""

    def __init__(self, existing_records=None):
        self.records = existing_records or {}
        self.update_success_calls = []
        self.update_failure_calls = []

    def get_delivery_record(self, report_date, recipient):
        key = f"{report_date}:{recipient}"
        return self.records.get(key)

    def record_delivery_attempt(self, record):
        key = f"{record.report_date}:{record.recipient}"
        self.records[key] = record
        return f"rec_{record.report_date}"

    def update_delivery_success(self, report_identifier, provider_message_id):
        self.update_success_calls.append((report_identifier, provider_message_id))
        for r in self.records.values():
            if r.report_identifier == report_identifier:
                r.delivery_status = "sent"
                r.provider_message_id = provider_message_id

    def update_delivery_failure(self, report_identifier, error_message):
        self.update_failure_calls.append((report_identifier, error_message))
        for r in self.records.values():
            if r.report_identifier == report_identifier:
                r.delivery_status = "failed"
                r.last_error = error_message

    def get_daily_summary_counts(self, report_date):
        return DailyReportMetadata(report_date=report_date, newly_promoted_count=0)


class TestNotificationDelivery:
    """Test suite for daily report email delivery, templates, and idempotency."""

    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def teardown_method(self):
        self.temp_dir.cleanup()

    def test_successful_delivery_with_excel_attachment(self):
        """Verifies report with new opportunities is delivered with exactly 1 Excel attachment."""
        sender = MockEmailSender(should_fail=False)
        repo = MockDeliveryRepository()
        service = NotificationDeliveryService(
            repository=repo,
            email_sender=sender,
            delivery_enabled=True,
            default_recipient="test@cyberscout.ai",
        )

        sample_opp = Opportunity(
            id="opp-test-1",
            title="Summer Cyber Security Internship",
            url="https://cyber.example.com",
            source_id="tavily",
            company="CERT-In",
            category="internship",
            deadline="2027-06-30",
            score=92,
        )

        meta = DailyReportMetadata(
            report_date="2026-11-13",
            newly_promoted_count=1,
            total_active_production=50,
        )

        result = service.deliver_daily_report(
            report_date="2026-11-13",
            metadata=meta,
            new_opportunities=[sample_opp],
            dry_run=False,
        )

        assert result["status"] == "success"
        assert len(sender.sent_emails) == 1
        sent = sender.sent_emails[0]
        assert sent["recipient"] == "test@cyberscout.ai"
        assert len(sent["attachments"]) == 1
        assert str(sent["attachments"][0]).endswith(".xlsx")
        assert len(repo.update_success_calls) == 1

    def test_idempotent_duplicate_prevention(self):
        """Verifies report for same date and recipient is NOT sent twice."""
        existing_rec = EmailDeliveryRecord(
            report_date="2026-11-13",
            recipient="test@cyberscout.ai",
            report_identifier="daily_report_2026-11-13_test_at_cyberscout.ai",
            delivery_status="sent",
            provider_message_id="brevo-prev-12345",
        )
        repo = MockDeliveryRepository(existing_records={"2026-11-13:test@cyberscout.ai": existing_rec})
        sender = MockEmailSender(should_fail=False)
        service = NotificationDeliveryService(
            repository=repo,
            email_sender=sender,
            delivery_enabled=True,
            default_recipient="test@cyberscout.ai",
        )

        result = service.deliver_daily_report(
            report_date="2026-11-13",
            new_opportunities=[],
            dry_run=False,
        )

        assert result["status"] == "skipped"
        assert "Already delivered" in result["reason"]
        assert len(sender.sent_emails) == 0, "No duplicate email should be transmitted"

    def test_status_only_email_when_no_new_opportunities(self):
        """Verifies status-only email without attachment when 0 new opportunities discovered."""
        sender = MockEmailSender(should_fail=False)
        repo = MockDeliveryRepository()
        service = NotificationDeliveryService(
            repository=repo,
            email_sender=sender,
            delivery_enabled=True,
            default_recipient="test@cyberscout.ai",
        )

        result = service.deliver_daily_report(
            report_date="2026-11-13",
            new_opportunities=[],
            dry_run=False,
        )

        assert result["status"] == "success"
        assert len(sender.sent_emails) == 1
        sent = sender.sent_emails[0]
        assert len(sent["attachments"]) == 0, "Empty report must NOT attach empty Excel workbook"
        assert "No New Opportunities" in sent["subject"]

    def test_failed_delivery_records_error_and_does_not_mark_sent(self):
        """Verifies delivery failure is tracked and never marked as sent."""
        sender = MockEmailSender(should_fail=True)
        repo = MockDeliveryRepository()
        service = NotificationDeliveryService(
            repository=repo,
            email_sender=sender,
            delivery_enabled=True,
            default_recipient="test@cyberscout.ai",
        )

        result = service.deliver_daily_report(
            report_date="2026-11-13",
            new_opportunities=[],
            dry_run=False,
        )

        assert result["status"] == "failed"
        assert len(repo.update_failure_calls) == 1
        assert len(repo.update_success_calls) == 0
