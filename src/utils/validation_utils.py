"""
Validation utilities for CyberScout AI.
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import uuid

from src.models.enums import OpportunityCategory


def is_valid_url(url: str) -> bool:
    """
    Validates whether a string is a valid HTTP/HTTPS URL.

    Args:
        url: Input URL string.

    Returns:
        True if valid URL, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def is_valid_uuid(uuid_str: str) -> bool:
    """
    Validates whether a string is a valid UUID v4 string.

    Args:
        uuid_str: Input UUID string.

    Returns:
        True if valid UUID v4, False otherwise.
    """
    if not uuid_str or not isinstance(uuid_str, str):
        return False

    try:
        val = uuid.UUID(uuid_str.strip(), version=4)
        return str(val) == uuid_str.strip()
    except ValueError:
        return False


def is_valid_email(email: str) -> bool:
    """
    Validates whether a string is a properly formatted email address.

    Args:
        email: Input email string.

    Returns:
        True if valid email format, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def is_valid_date(date_str: str) -> bool:
    """
    Validates whether a string is an ISO 8601 date string (YYYY-MM-DD or ISO timestamp).

    Args:
        date_str: Date string.

    Returns:
        True if valid date, False otherwise.
    """
    if not date_str or not isinstance(date_str, str):
        return False

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            datetime.strptime(date_str.strip(), fmt)
            return True
        except ValueError:
            continue
    try:
        datetime.fromisoformat(date_str.strip())
        return True
    except ValueError:
        return False


def is_valid_category(category_str: str) -> bool:
    """
    Validates whether a string matches a recognized OpportunityCategory enum.

    Args:
        category_str: Category string.

    Returns:
        True if recognized category, False otherwise.
    """
    if not category_str or not isinstance(category_str, str):
        return False
    return category_str.lower().strip() in set(OpportunityCategory)


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
    """
    Checks if all required keys are present and non-empty in a dictionary.

    Args:
        data: Input dictionary.
        required_fields: List of key names.

    Returns:
        Tuple of (is_valid, list_of_missing_keys).
    """
    missing = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            missing.append(field)
    return len(missing) == 0, missing
