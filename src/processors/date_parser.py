"""
Date Parsing and Normalization Helper for CyberScout AI.
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from src.utils.date_utils import parse_iso_date


def parse_and_format_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parses raw date string and returns standard ISO 8601 YYYY-MM-DD format.

    Args:
        date_str: Raw date string.

    Returns:
        Formatted YYYY-MM-DD string, or None if unparseable.
    """
    if not date_str or not isinstance(date_str, str) or not date_str.strip():
        return None

    cleaned = date_str.strip()

    dt = parse_iso_date(cleaned)
    if dt:
        return dt.strftime("%Y-%m-%d")

    # Common date formats (English textual dates, RSS dates, etc.)
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y/%m/%d",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    import re
    # Regex search for text patterns like "August 31, 2026" or "31 August 2026"
    match = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", cleaned, re.IGNORECASE)
    if match:
        m, d, y = match.group(1), match.group(2), match.group(3)
        try:
            parsed = datetime.strptime(f"{m} {d} {y}", "%b %d %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    match2 = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+(\d{4})\b", cleaned, re.IGNORECASE)
    if match2:
        d, m, y = match2.group(1), match2.group(2), match2.group(3)
        try:
            parsed = datetime.strptime(f"{d} {m} {y}", "%d %b %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def extract_dates_from_text(text: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Extracts published/release date and application deadline from free text contextually.

    Returns:
        Dict with keys "published_date" and "deadline".
    """
    import re
    results: Dict[str, Optional[str]] = {"published_date": None, "deadline": None}
    if not text or not isinstance(text, str):
        return results

    # Deadline Context Triggers
    deadline_patterns = [
        r"(?:deadline|apply by|applications close|registration closes|submission deadline|last date to apply|due date)\s*:\s*([A-Za-z0-9\s,/\-]+)",
        r"(?:apply before|closes on|due on)\s+([A-Za-z0-9\s,/\-]+)",
    ]
    for pat in deadline_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip().split(".")[0].split("\n")[0]
            parsed = parse_and_format_date(candidate)
            if parsed:
                results["deadline"] = parsed
                break

    # Published / Release Date Context Triggers
    release_patterns = [
        r"(?:published|release date|posted on|applications open|registration opens|starts on|published on)\s*:\s*([A-Za-z0-9\s,/\-]+)",
        r"(?:posted|published|opened)\s+on\s+([A-Za-z0-9\s,/\-]+)",
    ]
    for pat in release_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip().split(".")[0].split("\n")[0]
            parsed = parse_and_format_date(candidate)
            if parsed:
                results["published_date"] = parsed
                break

    return results
