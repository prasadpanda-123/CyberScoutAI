"""
Date Parsing and Normalization Helper for CyberScout AI.
"""

from datetime import datetime, timezone
from typing import Optional
from src.utils.date_utils import parse_iso_date


def parse_and_format_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parses raw date string and returns standard ISO 8601 YYYY-MM-DD format.

    Args:
        date_str: Raw date string.

    Returns:
        Formatted YYYY-MM-DD string, or None if unparseable.
    """
    if not date_str or not date_str.strip():
        return None

    dt = parse_iso_date(date_str)
    if dt:
        return dt.strftime("%Y-%m-%d")

    # Try common RSS date formats
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ]:
        try:
            parsed = datetime.strptime(date_str.strip(), fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None
