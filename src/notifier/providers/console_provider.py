"""
Console / Mock Email Provider for CyberScout AI.

Logs email message details to console for local testing or offline environments.
"""

import os
from typing import Any, Dict, List, Optional
import uuid

from src.core.logging import get_logger
from src.notifier.providers.base import BaseEmailProvider

logger = get_logger(__name__)


class ConsoleEmailProvider(BaseEmailProvider):
    """
    Console mock provider that prints email metadata without sending network requests.
    """

    @property
    def provider_name(self) -> str:
        return "console"

    def check_health(self) -> Dict[str, Any]:
        """Console provider is always healthy."""
        return {
            "provider": self.provider_name,
            "is_healthy": True,
            "dns": "OK",
            "tcp": "OK",
            "smtp": "OK",
            "message": "Console mock provider ready.",
        }

    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        attachments: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Logs mock email dispatch."""
        msg_id = f"<console-{uuid.uuid4()}@cyberscout.ai>"
        recipient = (os.getenv("EMAIL_TO") or "user@example.com").strip()
        att_count = len(attachments) if attachments else 0

        logger.info(
            f"[Console Provider] Dispatched Email:\n"
            f"  Subject     : {subject}\n"
            f"  Recipient   : {recipient}\n"
            f"  Attachments : {att_count}\n"
            f"  Message-ID  : {msg_id}"
        )

        return {
            "status": "success",
            "provider": self.provider_name,
            "message_id": msg_id,
            "recipient": recipient,
            "attachments_count": att_count,
        }
