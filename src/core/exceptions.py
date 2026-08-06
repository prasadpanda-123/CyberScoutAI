"""
Custom exceptions for the CyberScout AI application.

Provides a clean exception hierarchy rooted at CyberScoutError.
"""

from typing import Optional


class CyberScoutError(Exception):
    """Base exception class for all CyberScout AI errors."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception

    def __str__(self) -> str:
        if self.original_exception:
            return f"{self.message} (Caused by: {self.original_exception})"
        return self.message


class ConfigurationError(CyberScoutError):
    """Exception raised for configuration loading or validation errors."""

    pass


class DatabaseError(CyberScoutError):
    """Base exception raised for PostgreSQL database operations or schema errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Exception raised when PostgreSQL database connection fails or drops."""

    pass


class MigrationError(DatabaseError):
    """Exception raised during database schema migration failures."""

    pass


class QueryError(DatabaseError):
    """Exception raised for invalid or failing SQL query execution."""

    pass


class IntegrityError(DatabaseError):
    """Exception raised for database constraint/foreign key violations."""

    pass


class RepositoryError(DatabaseError):
    """Exception raised for generic Data Access Object (repository) errors."""

    pass


class CollectorError(CyberScoutError):
    """Exception raised for error during data collection from internet sources."""

    pass


class ValidationError(CyberScoutError):
    """Exception raised when model validation fails."""

    pass


class PipelineError(CyberScoutError):
    """Exception raised for errors in processing pipeline execution."""

    pass


class SchedulerError(CyberScoutError):
    """Exception raised for scheduling errors."""

    pass


class NetworkError(CyberScoutError):
    """Exception raised for HTTP or network timeouts and errors."""

    pass


class NotifierError(CyberScoutError):
    """Exception raised for email rendering or SMTP transmission errors."""

    pass


class IntelligenceError(CyberScoutError):
    """Exception raised for scoring, taxonomy, or search intelligence errors."""

    pass
