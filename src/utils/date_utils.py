"""
Date and time utilities for CyberScout AI.
"""

from datetime import datetime, timezone
from typing import Optional


def get_utc_now() -> datetime:
    """Returns current UTC datetime object."""
    return datetime.now(timezone.utc)


def get_utc_now_iso() -> str:
    """Returns current UTC datetime formatted as ISO 8601 string."""
    return get_utc_now().isoformat()


def get_today_iso() -> str:
    """Returns current UTC date formatted as YYYY-MM-DD string."""
    return get_utc_now().strftime("%Y-%m-%d")


def parse_iso_date(date_str: str) -> Optional[datetime]:
    """
    Parses an ISO date string (YYYY-MM-DD or full ISO format) into a datetime object.

    Args:
        date_str: String date representation.

    Returns:
        datetime object if successful, None otherwise.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None
