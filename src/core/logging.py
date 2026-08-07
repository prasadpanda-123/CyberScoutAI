"""
Centralized logging for the CyberScout AI application.

Supports stdout, rotating file logging, and PostgreSQL AppLogs table persistence.
"""

import logging
import logging.handlers
from pathlib import Path
import traceback
from typing import Optional

from src.core.constants import DEFAULT_LOG_FORMAT, LOGS_DIR


import threading

_logging_local = threading.local()


class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler persisting structured log records into AppLogs table.
    Includes thread-local re-entrancy guard to prevent recursive log loops.
    """

    def __init__(self, level=logging.NOTSET):
        super().__init__(level=level)
        self._repo = None

    @property
    def repo(self):
        if self._repo is None:
            try:
                from src.database.log_repository import LogRepository
                self._repo = LogRepository()
            except Exception:
                pass
        return self._repo

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_logging_local, "is_logging", False):
            return
        _logging_local.is_logging = True
        try:
            if not self.repo:
                return
            msg = record.getMessage()
            exc_text = None
            if record.exc_info:
                exc_text = "".join(traceback.format_exception(*record.exc_info))
            self.repo.insert_log(
                level=record.levelname,
                module=record.name or record.module or "app",
                message=msg,
                function_name=record.funcName,
                execution_time_ms=getattr(record, "execution_time_ms", None),
                exception_text=exc_text,
                correlation_id=getattr(record, "correlation_id", None),
            )
        except Exception:
            self.handleError(record)
        finally:
            _logging_local.is_logging = False


def setup_logging(
    level: str = "INFO",
    log_file_name: str = "cyberscout.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    Sets up the application's root logging configuration.

    Args:
        level: Minimum log level string (e.g. DEBUG, INFO, WARNING, ERROR).
        log_file_name: Name or path of the log file inside LOGS_DIR.
        max_bytes: Maximum size in bytes before log file rotation.
        backup_count: Number of rotated log files to retain.
        log_format: Optional custom log format string.

    Returns:
        The configured root logger instance.
    """
    fmt = log_format or DEFAULT_LOG_FORMAT
    log_level = getattr(logging, level.upper(), logging.INFO)

    filename_only = Path(log_file_name).name
    log_file = LOGS_DIR / filename_only

    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate log records
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter(fmt)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating File Handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Database Log Handler (PostgreSQL AppLogs Table)
    db_handler = DatabaseLogHandler(level=log_level)
    db_handler.setFormatter(formatter)
    root_logger.addHandler(db_handler)

    logging.info("Centralized logging system initialized with PostgreSQL AppLogs persistence.")
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger instance for use in any project module.

    Args:
        name: Usually __name__ of the calling module.

    Returns:
        A Logger instance.
    """
    return logging.getLogger(name)
