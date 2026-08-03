"""
Processor Exception Hierarchy for CyberScout AI.
"""

from src.core.exceptions import CyberScoutError


class ProcessingError(CyberScoutError):
    """Base exception for all processing pipeline errors."""

    pass


class ValidationError(ProcessingError):
    """Raised when an Opportunity fails structural or data validation."""

    pass


class QualityError(ProcessingError):
    """Raised when an Opportunity is rejected due to poor quality or spam."""

    pass
