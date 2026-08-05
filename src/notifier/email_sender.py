"""
Email Sender Facade for CyberScout AI.

Delegates email report transmission and health diagnostics to the active Brevo API provider.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.notifier.exceptions import NotificationError
from src.notifier.providers.factory import EmailProviderFactory

logger = get_logger(__name__)


class EmailSender:
    """
    Email transmission facade delegating report delivery and health diagnostics to Brevo REST API.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path

    def check_health(self) -> Dict[str, Any]:
        """
        Executes pre-flight connectivity and API authentication checks via Brevo API.
        """
        provider = EmailProviderFactory.get_provider()
        return provider.check_health()

    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        attachments: Optional[List[Any]] = None,
    ) -> str:
        """
        Transmits HTML/Text email report via Brevo REST API.

        Args:
            html_content: Email HTML body.
            plain_content: Fallback plain text body.
            subject: Email subject header.
            attachments: Optional list of filepaths.

        Returns:
            Message ID string on success.
        """
        provider = EmailProviderFactory.get_provider()
        res = provider.send_email(
            html_content=html_content,
            plain_content=plain_content,
            subject=subject,
            attachments=attachments,
        )

        if res.get("status") == "success":
            return res.get("message_id") or "brevo-sent"

        stage = res.get("stage", "MAIL_SEND")
        reason = res.get("reason", "Failed to transmit email")
        raise NotificationError(f"[{stage}] {reason}")
