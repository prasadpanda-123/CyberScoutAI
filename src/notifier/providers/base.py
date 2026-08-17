"""
Base interface and data models for CyberScout AI Email Providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseEmailProvider(ABC):
    """
    Abstract Base Class for email delivery provider adapters.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns string identifier of the provider."""
        pass

    @abstractmethod
    def send_email(
        self,
        html_content: str,
        plain_content: str,
        subject: str,
        recipient: Optional[Any] = None,
        attachments: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Sends email payload with optional attachments.

        Returns:
            Dictionary containing status, stage, message_id or error detail.
        """
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Executes pre-flight connectivity and credential diagnostics.

        Returns:
            Dictionary containing diagnostic test results.
        """
        pass
