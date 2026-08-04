"""
Intelligence & Quality Exception Hierarchy for CyberScout AI.
"""

from src.core.exceptions import CyberScoutError


class IntelligenceError(CyberScoutError):
    """Base exception class for all Intelligence Engine errors."""

    pass


class RankingError(IntelligenceError):
    """Raised when ranking computation fails."""

    pass


class RuleError(IntelligenceError):
    """Raised when a ranking rule evaluation fails."""

    pass


class QualityError(CyberScoutError):
    """Base exception class for all Quality Intelligence Engine errors."""

    pass


class RejectionError(QualityError):
    """Raised when an opportunity fails a quality evaluation stage."""

    def __init__(self, reason: str, details: str = ""):
        super().__init__(f"Quality Rejection [{reason}]: {details}")
        self.reason = reason
        self.details = details


class BlacklistMatchError(RejectionError):
    """Raised when an opportunity contains blacklisted terms or playlists."""

    def __init__(self, matched_term: str):
        super().__init__("BLACKLIST_KEYWORD", f"Matched blacklisted term: '{matched_term}'")
        self.matched_term = matched_term


class LowConfidenceError(RejectionError):
    """Raised when an opportunity's confidence score falls below minimum threshold."""

    def __init__(self, score: float, threshold: float):
        super().__init__("LOW_CONFIDENCE", f"Confidence score {score:.1f} is below threshold {threshold:.1f}")
        self.score = score
        self.threshold = threshold


class DuplicateOpportunityError(RejectionError):
    """Raised when an opportunity is identified as a duplicate."""

    def __init__(self, duplicate_of_id: str):
        super().__init__("DUPLICATE", f"Duplicate of existing opportunity '{duplicate_of_id}'")
        self.duplicate_of_id = duplicate_of_id
