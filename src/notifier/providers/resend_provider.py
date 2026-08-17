"""
Resend API Email Provider for CyberScout AI.

Sends email digests via Resend REST API over HTTPS port 443
using Python standard urllib.request (zero external dependencies).
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


class ResendEmailProvider(BaseEmailProvider):
    """
    Delivers email reports using Resend REST API (https://api.resend.com/emails).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.getenv("RESEND_API_KEY") or "").strip()
        self.api_url = "https://api.resend.com/emails"

    @property
    def provider_name(self) -> str:
        return "resend"

    def check_health(self) -> Dict[str, Any]:
        """Checks presence of Resend API Key."""
        if not self.api_key:
            return {
                "provider": self.provider_name,
                "is_healthy": False,
                "stage": "CONFIG",
                "reason": "Missing RESEND_API_KEY environment variable",
                "errors": ["Missing RESEND_API_KEY environment variable"],
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
        """Dispatches email via Resend API."""
        if not self.api_key:
            return {
                "status": "failed",
                "stage": "CONFIG",
                "reason": "Missing RESEND_API_KEY environment variable in Render Dashboard",
            }

        sender_email = (os.getenv("EMAIL_FROM") or os.getenv("RESEND_SENDER") or "onboarding@resend.dev").strip()
        raw_recipients = (os.getenv("EMAIL_TO") or os.getenv("RECIPIENT_EMAIL") or "user@example.com").strip()
        import re
        recipients = [e.strip() for e in re.split(r"[,;]", raw_recipients) if e.strip() and "@" in e]
        unique_recipients = list(dict.fromkeys(recipients))
        if not unique_recipients:
            unique_recipients = ["user@example.com"]

        payload: Dict[str, Any] = {
            "from": sender_email,
            "to": unique_recipients,
            "subject": subject,
            "html": html_content,
            "text": plain_content,
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
                        att_list.append({"filename": path.name, "content": b64_content})
                except Exception as e:
                    logger.warning(f"Resend: Could not encode attachment '{path.name}': {e}")
            if att_list:
                payload["attachments"] = att_list

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=data_bytes, method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_body = resp.read().decode("utf-8")
                res_json = json.loads(res_body)
                msg_id = res_json.get("id") or "resend-sent"
                logger.info(f"ResendEmailProvider: Email successfully sent. Message-ID: {msg_id}")
                return {
                    "status": "success",
                    "provider": self.provider_name,
                    "message_id": msg_id,
                    "recipient": ", ".join(unique_recipients),
                }
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="ignore")
            logger.error(f"Resend API error (HTTP {http_err.code}): {err_body}")
            return {
                "status": "failed",
                "stage": "MAIL_SEND",
                "reason": f"Resend API HTTP {http_err.code}: {err_body}",
            }
        except Exception as err:
            logger.error(f"Resend API request failed: {err}")
            return {"status": "failed", "stage": "MAIL_SEND", "reason": f"Resend request failed: {err}"}
