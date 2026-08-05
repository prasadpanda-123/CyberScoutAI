"""
Providers package for CyberScout AI Notifier.
"""

from src.notifier.providers.base import BaseEmailProvider
from src.notifier.providers.brevo_provider import BrevoEmailProvider
from src.notifier.providers.console_provider import ConsoleEmailProvider
from src.notifier.providers.factory import EmailProviderFactory
from src.notifier.providers.resend_provider import ResendEmailProvider
from src.notifier.providers.sendgrid_provider import SendGridEmailProvider

__all__ = [
    "BaseEmailProvider",
    "BrevoEmailProvider",
    "SendGridEmailProvider",
    "ResendEmailProvider",
    "ConsoleEmailProvider",
    "EmailProviderFactory",
]
