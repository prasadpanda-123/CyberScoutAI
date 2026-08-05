"""
Brevo (formerly Sendinblue) API Email Provider for CyberScout AI.

Sends transaction/digest emails via Brevo v3 REST API over HTTPS port 443
using Python standard urllib.request (zero third-party dependencies required).
"""

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

from src.core.logging import get_logger
from src.notifier.providers.base import BaseEmailProvider

logger = get_logger(__name__)


class BrevoEmailProvider(BaseEmailProvider):
    """
    Delivers email reports using Brevo REST API (https://api.brevo.com/v3/smtp/email).
    Works reliably on cloud hosts (like Render) where outbound port 587/25 may be restricted.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("BREVO_API_KEY") or os.getenv("SENDINBLUE_API_KEY") or "").strip()
        self.api_url = "https://api.brevo.com/v3/smtp/email"

    @property
    def provider_name(self) -> str:
        return "brevo"

    def check_health(self) -> Dict[str, Any]:
        """Checks presence of Brevo API Key."""
        if not self.api_key:
            return {
                "provider": self.provider_name,
                "is_healthy": False,
                "stage": "CONFIG",
                "reason": "Missing BREVO_API_KEY environment variable",
                "errors": ["Missing BREVO_API_KEY environment variable"],
            }
        return {
            "provider": self.provider_name,
            "is_healthy": True,
            "api_url": self.api_url,
            "api_key_configured": True,
        }

    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        attachments: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatches email via Brevo v3 REST API."""
        if not self.api_key:
            return {
                "status": "failed",
                "stage": "CONFIG",
                "reason": "Missing BREVO_API_KEY environment variable in Render Dashboard",
            }

        sender_email = (os.getenv("EMAIL_FROM") or os.getenv("BREVO_SENDER") or "cyberscout-alerts@example.com").strip()
        sender_name = os.getenv("EMAIL_SENDER_NAME") or "CyberScout AI"
        recipient_email = (os.getenv("EMAIL_TO") or os.getenv("RECIPIENT_EMAIL") or "user@example.com").strip()

        payload: Dict[str, Any] = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": recipient_email}],
            "subject": subject,
            "htmlContent": html_content,
            "textContent": plain_content,
        }

        # Encode attachments if present
        if attachments:
            att_list = []
            for att in attachments:
                path = Path(att)
                if not path.exists():
                    continue
                try:
                    with open(path, "rb") as f:
                        b64_content = base64.b64encode(f.read()).decode("utf-8")
                        att_list.append({"name": path.name, "content": b64_content})
                except Exception as e:
                    logger.warning(f"Brevo: Could not encode attachment '{path.name}': {e}")
            if att_list:
                payload["attachment"] = att_list

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=data_bytes, method="POST")
        req.add_header("api-key", self.api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_body = resp.read().decode("utf-8")
                res_json = json.loads(res_body)
                msg_id = res_json.get("messageId") or res_json.get("message_id") or "brevo-sent"
                logger.info(f"BrevoEmailProvider: Email successfully sent. Message-ID: {msg_id}")
                return {
                    "status": "success",
                    "provider": self.provider_name,
                    "message_id": msg_id,
                    "recipient": recipient_email,
                }
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="ignore")
            logger.error(f"Brevo API error (HTTP {http_err.code}): {err_body}")
            return {
                "status": "failed",
                "stage": "MAIL_SEND",
                "reason": f"Brevo API HTTP {http_err.code}: {err_body}",
            }
        except Exception as err:
            logger.error(f"Brevo API request failed: {err}")
            return {"status": "failed", "stage": "MAIL_SEND", "reason": f"Brevo request failed: {err}"}
