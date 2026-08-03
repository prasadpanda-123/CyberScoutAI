"""
Notification Engine package for CyberScout AI.
"""

from src.notifier.base import ReportDigest
from src.notifier.digest_builder import DigestBuilder
from src.notifier.email_client import EmailClient
from src.notifier.exceptions import (
    NotificationError,
    RenderError,
    SMTPError,
    TemplateError,
    RetryExceeded,
)
from src.notifier.history import HistoryTracker
from src.notifier.html_renderer import HTMLRenderer
from src.notifier.metrics import NotifierMetrics
from src.notifier.smtp_sender import SMTPSender
from src.notifier.template_loader import TemplateLoader

__all__ = [
    "EmailClient",
    "DigestBuilder",
    "HTMLRenderer",
    "TemplateLoader",
    "SMTPSender",
    "HistoryTracker",
    "NotifierMetrics",
    "ReportDigest",
    # Exceptions
    "NotificationError",
    "RenderError",
    "SMTPError",
    "TemplateError",
    "RetryExceeded",
]
