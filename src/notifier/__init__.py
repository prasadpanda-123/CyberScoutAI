"""
Notification Engine package for CyberScout AI.
"""

from src.notifier.base import ReportDigest
from src.notifier.digest_builder import DigestBuilder
from src.notifier.email_client import EmailClient
from src.notifier.email_sender import EmailSender
from src.notifier.exceptions import (
    NotificationError,
    RenderError,
    TemplateError,
    RetryExceeded,
)
from src.notifier.history import HistoryTracker
from src.notifier.html_renderer import HTMLRenderer
from src.notifier.metrics import NotifierMetrics
from src.notifier.template_loader import TemplateLoader

__all__ = [
    "EmailClient",
    "EmailSender",
    "DigestBuilder",
    "HTMLRenderer",
    "TemplateLoader",
    "HistoryTracker",
    "NotifierMetrics",
    "ReportDigest",
    # Exceptions
    "NotificationError",
    "RenderError",
    "TemplateError",
    "RetryExceeded",
]
