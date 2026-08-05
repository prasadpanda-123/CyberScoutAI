"""
Email Provider Factory for CyberScout AI.

Resolves active provider based on EMAIL_PROVIDER environment variable or configured API keys.
"""

import os
from typing import Dict, Type

from src.core.logging import get_logger
from src.notifier.providers.base import BaseEmailProvider
from src.notifier.providers.brevo_provider import BrevoEmailProvider
from src.notifier.providers.console_provider import ConsoleEmailProvider
from src.notifier.providers.resend_provider import ResendEmailProvider
from src.notifier.providers.sendgrid_provider import SendGridEmailProvider
from src.notifier.providers.smtp_provider import SMTPEmailProvider

logger = get_logger(__name__)


class EmailProviderFactory:
    """
    Factory creating configured BaseEmailProvider adapters.
    """

    _PROVIDERS: Dict[str, Type[BaseEmailProvider]] = {
        "smtp": SMTPEmailProvider,
        "gmail": SMTPEmailProvider,
        "brevo": BrevoEmailProvider,
        "sendinblue": BrevoEmailProvider,
        "sendgrid": SendGridEmailProvider,
        "resend": ResendEmailProvider,
        "console": ConsoleEmailProvider,
        "mock": ConsoleEmailProvider,
    }

    @classmethod
    def get_provider(cls, name: str = None) -> BaseEmailProvider:
        """
        Instantiates provider matching target name or EMAIL_PROVIDER env variable.
        Auto-detects API keys if EMAIL_PROVIDER is unconfigured.
        """
        provider_name = (name or os.getenv("EMAIL_PROVIDER") or "").strip().lower()

        if not provider_name:
            if os.getenv("BREVO_API_KEY") or os.getenv("SENDINBLUE_API_KEY"):
                provider_name = "brevo"
            elif os.getenv("RESEND_API_KEY"):
                provider_name = "resend"
            elif os.getenv("SENDGRID_API_KEY"):
                provider_name = "sendgrid"
            else:
                provider_name = "smtp"

        provider_cls = cls._PROVIDERS.get(provider_name)

        if not provider_cls:
            logger.warning(
                f"Unknown EMAIL_PROVIDER '{provider_name}'. Falling back to 'smtp' provider."
            )
            provider_cls = SMTPEmailProvider

        return provider_cls()
