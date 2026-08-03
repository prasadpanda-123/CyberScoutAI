"""
Company and Provider Extraction Helper for CyberScout AI.
"""

from typing import Optional
import re


def extract_company_name(title: str, provider: Optional[str] = None) -> Optional[str]:
    """
    Extracts company name from title string pattern (e.g. "Software Intern at Google for Py").

    Args:
        title: Target title string.
        provider: Fallback provider string.

    Returns:
        Extracted company name string, or provider fallback.
    """
    # Look for "at <Company>" stopping at prepositions like "for", "in", "with", or end of string/dashes
    match = re.search(r"\bat\b\s+([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+)*)", title)
    if match:
        company_candidate = match.group(1).strip()
        # Avoid matching common non-company words
        if company_candidate.lower() not in ["the", "a", "an"]:
            return company_candidate

    return provider
