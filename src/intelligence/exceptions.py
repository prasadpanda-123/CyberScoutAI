"""
Intelligence Exception Hierarchy for CyberScout AI.
"""

from src.core.exceptions import CyberScoutError


class IntelligenceError(CyberScoutError):
    """Base exception for intelligence and ranking engine errors."""

    pass


class RankingError(IntelligenceError):
    """Raised when scoring or ranking calculation fails."""

    pass


class RuleError(IntelligenceError):
    """Raised when rule evaluation encounters invalid parameters."""

    pass
