"""
Collector Exception Hierarchy for CyberScout AI.
"""

from src.core.exceptions import CyberScoutError


class CollectorError(CyberScoutError):
    """Base exception for all collector framework errors."""

    pass


class HTTPClientError(CollectorError):
    """Raised when an HTTP request fails or returns an unretryable error."""

    pass


class RateLimitError(CollectorError):
    """Raised when rate limits are exceeded or 429 status code is received."""

    pass


class RobotsForbiddenError(CollectorError):
    """Raised when crawling a target path is disallowed by robots.txt in strict mode."""

    pass


class ParsingError(CollectorError):
    """Raised when parsing raw HTML, JSON, or RSS content fails."""

    pass
