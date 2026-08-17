"""
Email Provider Factory for CyberScout AI.

Instantiates Brevo API as primary email provider with support for auxiliary providers.
"""

import os
from typing import Dict, Type

from src.core.logging import get_logger
from src.notifier.providers.base import BaseEmailProvider
from src.notifier.providers.brevo_provider import BrevoEmailProvider
from src.notifier.providers.console_provider import ConsoleEmailProvider
from src.notifier.providers.resend_provider import ResendEmailProvider
from src.notifier.providers.sendgrid_provider import SendGridEmailProvider
from src.notifier.providers.smtp_provider import SmtpEmailProvider

logger = get_logger(__name__)


class EmailProviderFactory:
    """
    Factory creating configured BaseEmailProvider adapters.
    Brevo REST API is the primary default provider.
    """

    _PROVIDERS: Dict[str, Type[BaseEmailProvider]] = {
        "smtp": SmtpEmailProvider,
        "mail": SmtpEmailProvider,
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
        Defaults to Brevo REST API.
        """
        provider_name = (name or os.getenv("EMAIL_PROVIDER") or "brevo").strip().lower()

        provider_cls = cls._PROVIDERS.get(provider_name)

        if not provider_cls:
            logger.warning(
                f"Unknown EMAIL_PROVIDER '{provider_name}'. Falling back to 'brevo' provider."
            )
            provider_cls = BrevoEmailProvider

        return provider_cls()
