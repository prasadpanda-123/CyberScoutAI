"""
String manipulation and hashing utilities for CyberScout AI.
"""

import hashlib
import re
from typing import Optional


def clean_text(text: Optional[str]) -> str:
    """
    Strips HTML tags, collapses consecutive whitespaces, and trims text.

    Args:
        text: Input string.

    Returns:
        Cleaned text string.
    """
    if not text:
        return ""

    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def truncate_string(text: Optional[str], max_length: int = 2000, suffix: str = "...") -> str:
    """
    Truncates a string to a specified length, appending suffix if truncated.

    Args:
        text: Input string.
        max_length: Maximum allowed length.
        suffix: Trailing indicator string.

    Returns:
        Truncated string.
    """
    if not text:
        return ""

    text = text.strip()
    if len(text) <= max_length:
        return text

    cutoff = max_length - len(suffix)
    return text[:cutoff] + suffix


def generate_url_hash(url: str) -> str:
    """
    Generates a 64-character SHA-256 hash of a normalized URL string.

    Args:
        url: Canonical target URL string.

    Returns:
        Hexadecimal SHA-256 hash string.
    """
    if not url:
        return ""
    normalized_url = url.strip().rstrip("/").lower()
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
