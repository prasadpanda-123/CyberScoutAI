"""
SMTP / Multi-Provider Email Sender Facade for CyberScout AI.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger
from src.core.smtp_validator import SMTPValidator
from src.notifier.exceptions import SMTPError
from src.notifier.providers.factory import EmailProviderFactory
from src.notifier.retry import retry_smtp

logger = get_logger(__name__)


class SMTPSender:
    """
    Email transmission facade supporting pluggable providers (Gmail SMTP, Brevo,
    SendGrid, Resend, Console) with dual-stack socket fallback and diagnostic monitoring.
    """

    def __init__(self, config_path: Optional[Path] = None, validator: Optional[SMTPValidator] = None):
        self.config_path = config_path or (CONFIG_DIR / "email.yaml")
        self.validator = validator or SMTPValidator(config_path=self.config_path)

        self.sender = ""
        self.recipient = ""
        self.smtp_host = ""
        self.smtp_port = 587
        self.smtp_user = ""
        self.smtp_pass = ""
        self.tls = True
        self.ssl_enabled = False
        self.retry_count = 3

        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads and validates SMTP configuration parameters."""
        cfg = self.validator.get_smtp_config()
        self.smtp_host = cfg["smtp_host"]
        try:
            self.smtp_port = int(cfg["smtp_port_raw"])
        except ValueError:
            self.smtp_port = 587
        self.smtp_user = cfg["smtp_username"]
        self.smtp_pass = cfg["smtp_password"]
        self.sender = cfg["email_from"]
        self.recipient = cfg["email_to"]
        self.tls = cfg["tls_enabled"]
        self.ssl_enabled = cfg["ssl_enabled"]

    def check_health(self) -> Dict[str, Any]:
        """
        Executes pre-flight connectivity and credential diagnostics using active provider.
        """
        provider = EmailProviderFactory.get_provider()
        return provider.check_health()

    def validate_startup(self) -> None:
        """
        Validates email configuration presence and provider reachability.
        Raises SMTPError on failure.
        """
        provider = EmailProviderFactory.get_provider()
        diag = provider.check_health()
        if not diag.get("is_healthy"):
            err_msg = diag.get("reason") or (diag.get("errors")[0] if diag.get("errors") else "Health check failed")
            raise SMTPError(f"Email Provider Diagnostics Failed: {err_msg}")

    @retry_smtp(attempts=3, delay_secs=1.0)
    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        attachments: Optional[list] = None,
    ) -> str:
        """
        Transmits HTML/Text email report via active provider.

        Args:
            html_content: Email HTML body.
            plain_content: Fallback plain text body.
            subject: Email subject header.
            attachments: Optional list of filepaths.

        Returns:
            Generated message id string.
        """
        provider = EmailProviderFactory.get_provider()
        res = provider.send_email(
            html_content=html_content,
            plain_content=plain_content,
            subject=subject,
            attachments=attachments,
        )

        if res.get("status") == "success":
            return res.get("message_id") or "sent-ok"

        stage = res.get("stage", "MAIL_SEND")
        reason = res.get("reason", "Failed to transmit email")
        raise SMTPError(f"[{stage}] {reason}")
