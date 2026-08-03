"""
Database & Knowledge Exception Hierarchy for CyberScout AI.
"""

from src.core.exceptions import CyberScoutError


class KnowledgeError(CyberScoutError):
    """Base exception for Knowledge Base and state tracking errors."""

    pass


class RetentionError(KnowledgeError):
    """Raised when retention policy execution or cleanup fails."""

    pass
