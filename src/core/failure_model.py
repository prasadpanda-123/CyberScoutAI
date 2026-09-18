"""
Failure Classification Model for CyberScout AI (Phase 10).

Provides deterministic, structured categorization of runtime, database,
network, and business exceptions to drive automated recovery, retry bounds,
and auditable telemetry.
"""

from dataclasses import dataclass
from enum import Enum
import socket
from typing import Any, Optional


class FailureCategory(str, Enum):
    """Classification of failure domains in the application."""
    TRANSIENT = "TRANSIENT"            # Temporary network blip, lock timeout, connection reset (retryable)
    PERMANENT = "PERMANENT"            # 404 Not Found, unsupported protocol, permanently dead endpoint
    DATA = "DATA"                      # Corrupt payload, schema validation error, invalid URL format
    CONFIGURATION = "CONFIGURATION"    # Missing secret, invalid environment variable, bad port
    AUTHENTICATION = "AUTHENTICATION"  # Bad password, expired session, invalid MFA token
    AUTHORIZATION = "AUTHORIZATION"    # RBAC failure, forbidden resource access, RLS violation
    DEPENDENCY = "DEPENDENCY"          # External provider down (e.g. Brevo, Ctftime, GitHub)
    PROGRAMMING = "PROGRAMMING"        # AttributeError, TypeError, NameError, syntax error
    UNKNOWN = "UNKNOWN"                # Unclassified fallback exception


@dataclass
class FailureCategoryInfo:
    """Structured information regarding a classified failure."""
    category: FailureCategory
    is_retryable: bool
    description: str
    suggested_action: str

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "is_retryable": self.is_retryable,
            "description": self.description,
            "suggested_action": self.suggested_action,
        }


def classify_failure(
    exception_or_status: Any,
    context: Optional[dict] = None,
) -> FailureCategoryInfo:
    """
    Deterministically maps an exception, HTTP status code, or error string
    into a structured FailureCategoryInfo object.

    Args:
        exception_or_status: Exception instance, int HTTP status, or error string.
        context: Optional dictionary with operational metadata.

    Returns:
        FailureCategoryInfo detailing category, retryability, and guidance.
    """
    ctx = context or {}

    # 1. HTTP Status Code Mapping
    if isinstance(exception_or_status, int):
        status = exception_or_status
        if status in (401,):
            return FailureCategoryInfo(
                category=FailureCategory.AUTHENTICATION,
                is_retryable=False,
                description="Invalid credentials or authentication challenge required.",
                suggested_action="Verify user identity or renew authentication session.",
            )
        elif status in (403,):
            return FailureCategoryInfo(
                category=FailureCategory.AUTHORIZATION,
                is_retryable=False,
                description="Access denied by role-based access control or security policy.",
                suggested_action="Verify account permissions and role assignments.",
            )
        elif status in (400, 422):
            return FailureCategoryInfo(
                category=FailureCategory.DATA,
                is_retryable=False,
                description="Malformed request payload or validation schema failure.",
                suggested_action="Correct data format and sanitize request inputs.",
            )
        elif status in (404, 410):
            return FailureCategoryInfo(
                category=FailureCategory.PERMANENT,
                is_retryable=False,
                description="Requested resource does not exist or has been permanently removed.",
                suggested_action="Do not retry. Update or archive target resource record.",
            )
        elif status in (408, 429, 502, 503, 504):
            return FailureCategoryInfo(
                category=FailureCategory.TRANSIENT,
                is_retryable=True,
                description=f"Upstream service temporarily unavailable or rate limited (HTTP {status}).",
                suggested_action="Apply bounded exponential backoff retry.",
            )
        elif status >= 500:
            return FailureCategoryInfo(
                category=FailureCategory.DEPENDENCY,
                is_retryable=True,
                description=f"Upstream dependency internal server error (HTTP {status}).",
                suggested_action="Log diagnostic telemetry and retry if within threshold.",
            )

    # 2. Exception Classification
    exc = exception_or_status
    exc_type = type(exc).__name__ if isinstance(exc, Exception) else str(exc)
    exc_msg = str(exc).lower()

    # Network / Transient Database Exceptions
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionResetError, ConnectionRefusedError, BrokenPipeError)):
        return FailureCategoryInfo(
            category=FailureCategory.TRANSIENT,
            is_retryable=True,
            description=f"Transient socket/network disruption: {exc_type}",
            suggested_action="Retry with exponential backoff.",
        )

    if any(term in exc_msg for term in (
        "connection closed", "connection reset", "pool timeout", "timeout expired",
        "lock timeout", "deadlock detected", "canceling statement due to lock timeout",
        "temporary failure", "could not connect to server", "connection refused",
    )):
        return FailureCategoryInfo(
            category=FailureCategory.TRANSIENT,
            is_retryable=True,
            description=f"Transient PostgreSQL/pool connectivity issue: {exc}",
            suggested_action="Reset connection pool and retry transactional operation.",
        )

    # Configuration Exceptions
    if any(term in exc_msg for term in (
        "environment variable is required", "missing secret", "configuration error",
        "invalid secret key", "unsupported database backend",
    )):
        return FailureCategoryInfo(
            category=FailureCategory.CONFIGURATION,
            is_retryable=False,
            description=f"Critical application configuration is invalid or missing: {exc}",
            suggested_action="Configure required environment variables and secrets before restart.",
        )

    # Data Validation / Integrity Exceptions
    if exc_type in ("IntegrityError", "ValidationError", "DataQualityError", "ValueError"):
        return FailureCategoryInfo(
            category=FailureCategory.DATA,
            is_retryable=False,
            description=f"Data integrity or validation rule failure: {exc}",
            suggested_action="Quarantine corrupt record or discard invalid input.",
        )

    # Authorization / Authentication Exceptions
    if any(term in exc_msg for term in ("permission denied", "access denied", "violates row-level security policy")):
        return FailureCategoryInfo(
            category=FailureCategory.AUTHORIZATION,
            is_retryable=False,
            description=f"Security access violation or RLS policy block: {exc}",
            suggested_action="Verify user identity and RLS policy rules.",
        )

    if any(term in exc_msg for term in ("invalid credentials", "invalid password", "bad otp", "csrf token")):
        return FailureCategoryInfo(
            category=FailureCategory.AUTHENTICATION,
            is_retryable=False,
            description=f"Authentication challenge failed: {exc}",
            suggested_action="Prompt user for valid credentials.",
        )

    # Programming Errors
    if isinstance(exc, (NameError, TypeError, AttributeError, SyntaxError, IndexError, KeyError, ZeroDivisionError)):
        return FailureCategoryInfo(
            category=FailureCategory.PROGRAMMING,
            is_retryable=False,
            description=f"Internal application logic error ({exc_type}): {exc}",
            suggested_action="Log detailed server traceback and report bug.",
        )

    # Fallback / Unknown
    return FailureCategoryInfo(
        category=FailureCategory.UNKNOWN,
        is_retryable=False,
        description=f"Unclassified failure: {exc}",
        suggested_action="Log exception and review application diagnostics.",
    )
