"""
Date Parsing, Normalization, and Validation Helper for CyberScout AI.
"""

from datetime import datetime, timezone
import re
from typing import Dict, Optional, Tuple
from src.utils.date_utils import parse_iso_date


# Precompiled regular expressions for high-throughput date parsing
RE_MONTH_DAY_YEAR = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
    re.IGNORECASE
)
RE_DAY_MONTH_YEAR = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[a-z]*,?\s+(\d{4})\b",
    re.IGNORECASE
)
RE_NUMERIC_YMD = re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b")
RE_NUMERIC_DMY = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b")

DEADLINE_PATTERNS = [
    re.compile(r"(?:deadline|apply by|applications close|registration closes|submission deadline|last date to apply|due date)\s*:\s*([A-Za-z0-9\s,/\-]+)", re.IGNORECASE),
    re.compile(r"(?:apply before|closes on|due on|ends on)\s+([A-Za-z0-9\s,/\-]+)", re.IGNORECASE),
]

RELEASE_PATTERNS = [
    re.compile(r"(?:published|release date|posted on|applications open|registration opens|starts on|published on|opening date)\s*:\s*([A-Za-z0-9\s,/\-]+)", re.IGNORECASE),
    re.compile(r"(?:posted|published|opened)\s+on\s+([A-Za-z0-9\s,/\-]+)", re.IGNORECASE),
]

EXACT_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d %b %Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d %Y",
    "%b %d %Y",
]


def parse_and_format_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parses raw date string and returns standard ISO 8601 YYYY-MM-DD format.
    Supports formats:
    - YYYY-MM-DD, YYYY/MM/DD
    - DD-MM-YYYY, DD/MM/YYYY
    - MM/DD/YYYY
    - DD Month YYYY, Month DD, YYYY
    - RFC 2822 / RSS timestamps
    - ISO 8601 timestamps (with/without timezone)

    Args:
        date_str: Raw date string.

    Returns:
        Formatted YYYY-MM-DD string, or None if unparseable or uncertain.
    """
    if not date_str or not isinstance(date_str, str) or not date_str.strip():
        return None

    cleaned = date_str.strip()

    # Fast path: exact ISO YYYY-MM-DD
    if len(cleaned) == 10 and cleaned[4] in "-/" and cleaned[7] in "-/":
        try:
            sep = cleaned[4]
            fmt = f"%Y{sep}%m{sep}%d"
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Fast path: Try ISO date utility
    dt = parse_iso_date(cleaned)
    if dt:
        return dt.strftime("%Y-%m-%d")

    # Regex search for text patterns like "August 15, 2026" or "15 August 2026"
    match = RE_MONTH_DAY_YEAR.search(cleaned)
    if match:
        m, d, y = match.group(1)[:3], match.group(2), match.group(3)
        try:
            parsed = datetime.strptime(f"{m} {d} {y}", "%b %d %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    match2 = RE_DAY_MONTH_YEAR.search(cleaned)
    if match2:
        d, m, y = match2.group(1), match2.group(2)[:3], match2.group(3)
        try:
            parsed = datetime.strptime(f"{d} {m} {y}", "%d %b %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Common exact date & datetime format strings
    for fmt in EXACT_DATE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    match2 = RE_DAY_MONTH_YEAR.search(cleaned)
    if match2:
        d, m, y = match2.group(1), match2.group(2)[:3], match2.group(3)
        try:
            parsed = datetime.strptime(f"{d} {m} {y}", "%d %b %Y")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Regex search for numeric dates: YYYY-MM-DD or DD-MM-YYYY or MM/DD/YYYY
    match_num = RE_NUMERIC_YMD.search(cleaned)
    if match_num:
        y, m, d = match_num.group(1), match_num.group(2), match_num.group(3)
        try:
            parsed = datetime(int(y), int(m), int(d))
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    match_dmy = RE_NUMERIC_DMY.search(cleaned)
    if match_dmy:
        p1, p2, y = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
        # If p1 > 12, p1 is day, p2 is month
        if 1 <= p2 <= 12 and 1 <= p1 <= 31:
            try:
                parsed = datetime(y, p2, p1)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                pass
        # Fallback to MM/DD/YYYY
        if 1 <= p1 <= 12 and 1 <= p2 <= 31:
            try:
                parsed = datetime(y, p1, p2)
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
    results: Dict[str, Optional[str]] = {"published_date": None, "deadline": None}
    if not text or not isinstance(text, str):
        return results

    # Deadline Context Triggers
    for pat in DEADLINE_PATTERNS:
        match = pat.search(text)
        if match:
            candidate = match.group(1).strip().split(".")[0].split("\n")[0]
            parsed = parse_and_format_date(candidate)
            if parsed:
                results["deadline"] = parsed
                break

    # Published / Release Date Context Triggers
    for pat in RELEASE_PATTERNS:
        match = pat.search(text)
        if match:
            candidate = match.group(1).strip().split(".")[0].split("\n")[0]
            parsed = parse_and_format_date(candidate)
            if parsed:
                results["published_date"] = parsed
                break

    return results


def validate_dates(release_date: Optional[str], deadline: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validates logical consistency of release_date and deadline (release_date <= deadline).

    Args:
        release_date: Release / published date string (YYYY-MM-DD).
        deadline: Deadline date string (YYYY-MM-DD).

    Returns:
        Tuple of (is_valid: bool, issue_description: Optional[str]).
    """
    if not release_date or not deadline:
        return True, None

    try:
        r_dt = datetime.strptime(release_date, "%Y-%m-%d")
        d_dt = datetime.strptime(deadline, "%Y-%m-%d")
        if r_dt > d_dt:
            return False, f"Logical date inconsistency: release_date ({release_date}) > deadline ({deadline})"
        return True, None
    except ValueError as e:
        return False, f"Date format validation error: {e}"

