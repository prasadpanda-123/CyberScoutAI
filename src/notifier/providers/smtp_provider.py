"""
SMTP Email Provider for CyberScout AI.

Delivers email reports and verification codes using standard SMTP transport (TLS/SSL).
"""

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from pathlib import Path
import re
import smtplib
import socket
import ssl
from typing import Any, Dict, List, Optional
import uuid

from src.core.logging import get_logger
from src.notifier.providers.base import BaseEmailProvider

logger = get_logger(__name__)


class SmtpEmailProvider(BaseEmailProvider):
    """
    Standard SMTP Provider supporting TLS/SSL transport with host, port, and credential configuration.
    """

    def __init__(self):
        self.host = (os.getenv("SMTP_HOST") or os.getenv("MAIL_SERVER") or "smtp-relay.brevo.com").strip()
        try:
            self.port = int(os.getenv("SMTP_PORT") or os.getenv("MAIL_PORT") or 587)
        except (ValueError, TypeError):
            self.port = 587
        self.username = (os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or os.getenv("MAIL_USERNAME") or "").strip()
        self.password = (os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS") or os.getenv("MAIL_PASSWORD") or "").strip()
        self.sender_email = (os.getenv("SMTP_FROM") or os.getenv("EMAIL_FROM") or os.getenv("MAIL_DEFAULT_SENDER") or self.username or "notifications@cyberscout.ai").strip()
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes") or self.port == 465

    @property
    def provider_name(self) -> str:
        return "smtp"

    def check_health(self) -> Dict[str, Any]:
        """
        Executes pre-flight DNS, TCP connectivity, and SMTP handshake checks.
        """
        # 1. DNS Resolution
        try:
            socket.gethostbyname(self.host)
            dns_status = "OK"
        except Exception as e:
            return {
                "provider": self.provider_name,
                "is_healthy": False,
                "stage": "DNS_CHECK",
                "dns": f"FAILED: {e}",
                "message": f"Could not resolve SMTP host '{self.host}'",
            }

        # 2. TCP Port Connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
            sock.close()
            tcp_status = "OK"
        except Exception as e:
            return {
                "provider": self.provider_name,
                "is_healthy": False,
                "stage": "TCP_CONNECT",
                "dns": dns_status,
                "tcp": f"FAILED: {e}",
                "message": f"Could not connect to {self.host}:{self.port}",
            }

        # 3. SMTP Handshake / Auth check (if credentials provided)
        smtp_status = "OK"
        if self.username and self.password:
            try:
                if self.use_ssl:
                    server = smtplib.SMTP_SSL(self.host, self.port, timeout=5.0)
                else:
                    server = smtplib.SMTP(self.host, self.port, timeout=5.0)
                    if self.use_tls:
                        server.starttls()
                server.login(self.username, self.password)
                server.quit()
            except Exception as e:
                smtp_status = f"AUTH_WARN: {e}"

        return {
            "provider": self.provider_name,
            "is_healthy": True,
            "dns": dns_status,
            "tcp": tcp_status,
            "smtp": smtp_status,
            "message": f"SMTP transport ({self.host}:{self.port}) operational.",
        }

    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        recipient: Optional[Any] = None,
        attachments: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Sends email message via SMTP transport with multipart HTML, plaintext, and attachments.
        """
        if recipient:
            if isinstance(recipient, str):
                raw_recipient = recipient.strip()
            elif isinstance(recipient, (list, tuple)):
                raw_recipient = ",".join(str(r) for r in recipient)
            else:
                raw_recipient = str(recipient)
        else:
            raw_recipient = (os.getenv("EMAIL_TO") or "user@example.com").strip()

        recipients = [e.strip() for e in re.split(r"[,;]", raw_recipient) if e.strip() and "@" in e]
        unique_recipients = list(dict.fromkeys(recipients))
        if not unique_recipients:
            unique_recipients = ["user@example.com"]

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = ", ".join(unique_recipients)
        msg_id = f"<{uuid.uuid4()}@{self.host}>"
        msg["Message-ID"] = msg_id

        # Alternative body (plain + HTML)
        alt_part = MIMEMultipart("alternative")
        if plain_content:
            alt_part.attach(MIMEText(plain_content, "plain", "utf-8"))
        if html_content:
            alt_part.attach(MIMEText(html_content, "html", "utf-8"))
        msg.attach(alt_part)

        # Attachments
        if attachments:
            for att in attachments:
                try:
                    att_path = Path(att)
                    if att_path.is_file():
                        with open(att_path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=att_path.name)
                        part["Content-Disposition"] = f'attachment; filename="{att_path.name}"'
                        msg.attach(part)
                except Exception as att_err:
                    logger.warning(f"Could not attach file '{att}': {att_err}")

        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, timeout=15.0, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(self.sender_email, unique_recipients, msg.as_string())
            else:
                with smtplib.SMTP(self.host, self.port, timeout=15.0) as server:
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(self.sender_email, unique_recipients, msg.as_string())

            logger.info(f"SMTP email successfully dispatched to {len(unique_recipients)} recipient(s). Message-ID: {msg_id}")
            return {
                "status": "success",
                "message_id": msg_id,
                "recipients_count": len(unique_recipients),
                "provider": "smtp",
            }
        except Exception as e:
            logger.error(f"SMTP delivery failed to {self.host}:{self.port}: {e}")
            return {
                "status": "error",
                "stage": "SMTP_DELIVERY",
                "reason": str(e),
                "provider": "smtp",
            }
