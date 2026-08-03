"""
Location and Remote/Hybrid Detection Helper for CyberScout AI.
"""

from typing import Tuple


def detect_location_and_remote(text: str) -> Tuple[bool, bool, str]:
    """
    Detects remote status, hybrid status, and location string from text.

    Args:
        text: Target description or location text.

    Returns:
        Tuple of (is_remote: bool, is_hybrid: bool, location_type_str: str).
    """
    text_lower = text.lower()
    is_remote = False
    is_hybrid = False
    loc_type = "Onsite"

    if any(k in text_lower for k in ["remote", "work from home", "virtual", "online", "anywhere"]):
        is_remote = True
        loc_type = "Remote"

    if "hybrid" in text_lower:
        is_hybrid = True
        loc_type = "Hybrid" if not is_remote else "Remote/Hybrid"

    return is_remote, is_hybrid, loc_type
