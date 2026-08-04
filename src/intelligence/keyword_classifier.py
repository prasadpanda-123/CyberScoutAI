"""
Stage 4: Cybersecurity Keyword Intelligence & Classifier Module for CyberScout AI.
"""

import re
from typing import List, Optional, Set, Tuple
from src.intelligence.quality_rules import QualityRules


class KeywordClassifier:
    """
    Scans title, description, README, topics, and homepage for cybersecurity domain keywords.
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def classify_keywords(
        self,
        title: str,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        topics: Optional[List[str]] = None,
        homepage: Optional[str] = None,
    ) -> Tuple[float, List[str]]:
        """
        Calculates keyword intelligence score and matched terms.

        Returns:
            Tuple of (keyword_score, list_of_matched_keywords)
        """
        combined_text = f"{title} {description or ''} {readme or ''} {' '.join(topics or [])} {homepage or ''}".lower()
        matched: Set[str] = set()

        for kw in self.rules.preferred_keywords:
            kw_clean = kw.lower()
            if len(kw_clean) <= 3:
                # Use word boundary matching for short acronyms like CVE, XSS, SOC, CTF
                pattern = rf"\b{re.escape(kw_clean)}\b"
                if re.search(pattern, combined_text):
                    matched.add(kw)
            else:
                if kw_clean in combined_text:
                    matched.add(kw)

        if not matched:
            return 0.0, []

        # Score calculation: 25 points per unique cybersecurity keyword match up to 100 max
        score = min(100.0, len(matched) * 25.0)
        return score, sorted(list(matched))
