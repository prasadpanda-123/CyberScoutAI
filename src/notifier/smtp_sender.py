"""
SMTP Email Sender for CyberScout AI.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from pathlib import Path
import smtplib
from typing import Optional
import uuid

from src.core.constants import CONFIG_DIR
from src.core.exceptions import ConfigurationError
from src.core.logging import get_logger
from src.core.smtp_validator import SMTPValidator
from src.notifier.exceptions import SMTPError
from src.notifier.retry import retry_smtp

logger = get_logger(__name__)


class SMTPSender:
    """
    SMTP transmission client supporting TLS, SSL, credentials authentication,
    and automatic startup configuration validation.
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

    def validate_startup(self) -> None:
        """
        Validates SMTP configuration presence and DNS reachability.
        Raises ConfigurationError or SMTPError on failure.
        """
        cfg = self.validator.validate_configuration()
        dns_ok, dns_msg = self.validator.verify_dns(cfg["smtp_host"])
        if not dns_ok:
            raise SMTPError(f"DNS resolution failed: {dns_msg}")

    @retry_smtp(attempts=3, delay_secs=1.0)
    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        attachments: Optional[list] = None,
    ) -> str:
        """
        Transmits HTML/Text email payload and optional file attachments via SMTP.

        Args:
            html_content: Email HTML body.
            plain_content: Fallback plain text body.
            subject: Email subject header.
            attachments: Optional list of Path or str filepaths.

        Returns:
            Generated message id string.
        """
        from email import encoders
        from email.mime.base import MIMEBase
        import mimetypes

        # Validate configuration & DNS before attempting network connection
        cfg = self.validator.validate_configuration()
        host = cfg["smtp_host"]
        port = cfg["smtp_port"]
        user = cfg["smtp_username"]
        password = cfg["smtp_password"]
        sender = cfg["email_from"]
        recipient = cfg["email_to"]

        dns_ok, dns_msg = self.validator.verify_dns(host)
        if not dns_ok:
            raise SMTPError(dns_msg)

        # Compile mime message (mixed container if attachments present)
        msg = MIMEMultipart("mixed") if attachments else MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        msg_id = f"<{uuid.uuid4()}@cyberscout.ai>"
        msg["Message-ID"] = msg_id

        if attachments:
            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(plain_content, "plain"))
            body_part.attach(MIMEText(html_content, "html"))
            msg.attach(body_part)

            for att in attachments:
                path = Path(att)
                if not path.exists():
                    logger.warning(f"Attachment file not found: {path}")
                    continue

                suffix = path.suffix.lower()
                if suffix == ".docx":
                    maintype, subtype = "application", "vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif suffix == ".csv":
                    maintype, subtype = "text", "csv"
                else:
                    mime_type, _ = mimetypes.guess_type(str(path))
                    if mime_type:
                        maintype, subtype = mime_type.split("/", 1)
                    else:
                        maintype, subtype = "application", "octet-stream"

                try:
                    with open(path, "rb") as f:
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename="{path.name}"',
                        )
                        msg.attach(part)
                        logger.info(f"Attached file '{path.name}' to email.")
                except Exception as att_err:
                    logger.error(f"Failed to attach file '{path}': {att_err}")
        else:
            msg.attach(MIMEText(plain_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

        try:
            if port == 465 or cfg["ssl_enabled"]:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                if cfg["tls_enabled"]:
                    server.starttls()

            if user and password:
                server.login(user, password)

            server.sendmail(sender, [recipient], msg.as_string())
            server.quit()
            logger.info(f"Email successfully delivered via SMTP to {recipient}. Message-ID: {msg_id}")
            return msg_id

        except Exception as e:
            logger.error(f"SMTP delivery failed: {e}")
            raise SMTPError(f"SMTP transmission error: {e}", original_exception=e)
