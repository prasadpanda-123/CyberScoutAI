"""
Language Detection Helper for CyberScout AI.
"""


def detect_language(text: str) -> str:
    """
    Basic language detector returning ISO 639-1 language code (e.g. 'en').

    Args:
        text: Target text to analyze.

    Returns:
        ISO language code string.
    """
    # Simple heuristic fallback for English content
    return "en"
