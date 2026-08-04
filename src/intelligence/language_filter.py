"""
Stage 3: Repository Programming Language Filter Module for CyberScout AI.
"""

from typing import Optional, Tuple
from src.intelligence.quality_rules import QualityRules


class LanguageFilter:
    """
    Evaluates primary programming language of a repository.
    Boosts preferred development languages and penalizes non-code repos (HTML-only, CSS-only).
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def evaluate_language(self, language: Optional[str]) -> Tuple[float, Optional[str]]:
        """
        Evaluates programming language quality score.

        Args:
            language: Primary programming language string (e.g. 'Python', 'Go', 'HTML').

        Returns:
            Tuple of (language_score, quality_flag)
        """
        if not language or not isinstance(language, str) or not language.strip():
            return 50.0, "NEUTRAL_LANGUAGE"

        clean_lang = language.strip().lower()
        approved = [l.lower() for l in self.rules.approved_languages]
        penalized = [l.lower() for l in self.rules.penalized_languages]

        if clean_lang in approved:
            return 100.0, "APPROVED_LANGUAGE"

        if clean_lang in penalized:
            return 10.0, "PENALIZED_LANGUAGE"

        return 40.0, "UNSUPPORTED_LANGUAGE"
