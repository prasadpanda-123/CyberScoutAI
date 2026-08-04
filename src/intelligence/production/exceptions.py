"""
Custom Exception hierarchy for Production Data Intelligence (Phase 12).
"""

from src.core.exceptions import CyberScoutError


class ProductionIntelligenceError(CyberScoutError):
    """Base exception for all Production Data Intelligence operations."""
    pass


class LinkValidationError(ProductionIntelligenceError):
    """Raised when link verification fails due to DNS, HTTP status, or dead URL."""
    pass


class ContentVerificationError(ProductionIntelligenceError):
    """Raised when content verification detects login gate, CAPTCHA, or domain parking."""
    pass


class ReliabilityCalculationError(ProductionIntelligenceError):
    """Raised when provider reliability scoring calculation fails."""
    pass
