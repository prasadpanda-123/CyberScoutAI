"""
SMTP Email Sender for CyberScout AI.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from pathlib import Path
import smtplib
from typing import Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger
from src.notifier.exceptions import SMTPError
from src.notifier.retry import retry_smtp

logger = get_logger(__name__)


class SMTPSender:
    """
    SMTP transmission client supporting TLS, SSL, credentials authentication.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (CONFIG_DIR / "email.yaml")
        self.sender = "cyberscout-alerts@example.com"
        self.recipient = "user@example.com"
        self.smtp_host = "smtp.example.com"
        self.smtp_port = 587
        self.tls = True
        self.retry_count = 3
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads SMTP configuration values."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.sender = data.get("sender", self.sender)
                self.recipient = data.get("recipient", self.recipient)
                self.smtp_host = data.get("smtp_host", self.smtp_host)
                self.smtp_port = int(data.get("smtp_port", self.smtp_port))
                self.tls = bool(data.get("tls", self.tls))
                self.retry_count = int(data.get("retry_count", self.retry_count))
            except Exception as e:
                logger.warning(f"Could not load email.yaml: {e}")

    @retry_smtp(attempts=3, delay_secs=1.0)
    def send_email(self, html_content: str, plain_content: str, subject: str) -> str:
        """
        Transmits HTML and plain text email payload via SMTP.

        Args:
            html_content: Email HTML body.
            plain_content: Fallback plain text body.
            subject: Email subject header.

        Returns:
            Generated message id string.
        """
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS")

        # Compile mime message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient

        import uuid
        msg_id = f"<{uuid.uuid4()}@cyberscout.ai>"
        msg["Message-ID"] = msg_id

        msg.attach(MIMEText(plain_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            # Handle SSL port vs TLS port
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                if self.tls:
                    server.starttls()

            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)

            server.sendmail(self.sender, [self.recipient], msg.as_string())
            server.quit()
            logger.info(f"Email successfully delivered via SMTP. Message-ID: {msg_id}")
            return msg_id

        except Exception as e:
            logger.error(f"SMTP delivery failed: {e}")
            raise SMTPError(f"SMTP transmission error: {e}", original_exception=e)
