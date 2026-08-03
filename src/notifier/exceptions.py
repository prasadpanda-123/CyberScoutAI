"""
Exception definitions for the Notifier Engine of CyberScout AI.
"""

from src.core.exceptions import CyberScoutError


class NotificationError(CyberScoutError):
    """Base exception class for all Notifier Engine errors."""

    pass


class RenderError(NotificationError):
    """Raised when template compilation or HTML/text rendering fails."""

    pass


class SMTPError(NotificationError):
    """Raised when SMTP connection, authorization, or transmission fails."""

    pass


class TemplateError(NotificationError):
    """Raised when loading or validating a Jinja template fails."""

    pass


class RetryExceeded(NotificationError):
    """Raised when all retry attempts to transmit notification are exhausted."""

    pass
