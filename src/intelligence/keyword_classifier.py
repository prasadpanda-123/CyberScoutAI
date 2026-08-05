"""
Stage 4: Cybersecurity Keyword Intelligence & Classifier Module for CyberScout AI.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from src.intelligence.quality_rules import QualityRules


class KeywordClassifier:
    """
    Scans repository metadata across all available fields: Title/Repo Name,
    Description, GitHub Topics, README, Homepage, URL, License, and Owner Type
    for comprehensive cybersecurity domain vocabulary.
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def _match_keywords_in_text(self, text: str) -> Set[str]:
        """Helper to find all matching keywords in a given string."""
        if not text or not text.strip():
            return set()

        text_lower = text.lower()
        matched: Set[str] = set()

        # Combine preferred keywords and approved topics for matching
        all_vocab = set(self.rules.preferred_keywords + self.rules.approved_topics)

        for kw in all_vocab:
            kw_clean = kw.lower().strip()
            if not kw_clean:
                continue
            if len(kw_clean) <= 3:
                # Use word boundary matching for short acronyms like CVE, XSS, SOC, CTF, HTB, THM, RCE
                pattern = rf"\b{re.escape(kw_clean)}\b"
                if re.search(pattern, text_lower):
                    matched.add(kw)
            else:
                # Direct substring match or boundary match
                if kw_clean in text_lower or kw_clean.replace("-", " ") in text_lower:
                    matched.add(kw)

        return matched

    def analyze_field_scores(
        self,
        title: str,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        topics: Optional[List[str]] = None,
        homepage: Optional[str] = None,
        url: Optional[str] = None,
        license_name: Optional[str] = None,
        owner_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes ALL available repository metadata fields and calculates weighted scores.

        Returns dictionary containing:
            - repo_name_score (0 - 20)
            - description_score (0 - 20)
            - topics_score (0 - 20)
            - readme_score (0 - 15)
            - matched_keywords (List[str])
        """
        # 1. Repository Name & Title text extraction
        url_part = ""
        if url:
            # Extract repository owner/name from URL e.g. https://github.com/bl4de/security-tools
            clean_url = url.replace("https://github.com/", "").replace("http://github.com/", "")
            url_part = clean_url.replace("/", " ").replace("-", " ").replace("_", " ")

        name_text = f"{title or ''} {url_part} {owner_type or ''} {license_name or ''}"
        name_matches = self._match_keywords_in_text(name_text)

        if len(name_matches) >= 2:
            repo_name_score = 20.0
        elif len(name_matches) == 1:
            repo_name_score = 15.0
        else:
            repo_name_score = 0.0

        # 2. Description text matching
        desc_text = f"{description or ''} {homepage or ''}"
        desc_matches = self._match_keywords_in_text(desc_text)

        if len(desc_matches) >= 3:
            description_score = 20.0
        elif len(desc_matches) == 2:
            description_score = 15.0
        elif len(desc_matches) == 1:
            description_score = 10.0
        else:
            description_score = 0.0

        # 3. Topics text matching
        topics_str = " ".join(topics or [])
        topic_matches = self._match_keywords_in_text(topics_str)

        if len(topic_matches) >= 3:
            topics_score = 20.0
        elif len(topic_matches) == 2:
            topics_score = 15.0
        elif len(topic_matches) == 1:
            topics_score = 10.0
        else:
            topics_score = 0.0

        # 4. README text matching
        if readme and readme.strip():
            readme_matches = self._match_keywords_in_text(readme)
            if len(readme_matches) >= 2:
                readme_score = 15.0
            elif len(readme_matches) == 1:
                readme_score = 8.0
            else:
                readme_score = 0.0
        else:
            readme_matches = set()
            # If README is not collected/available, fallback gracefully if metadata is strong
            metadata_sum = repo_name_score + description_score + topics_score
            if metadata_sum >= 25.0:
                readme_score = 10.0
            elif metadata_sum >= 10.0:
                readme_score = 8.0
            else:
                readme_score = 0.0

        all_matched = sorted(list(name_matches | desc_matches | topic_matches | readme_matches))

        return {
            "repo_name_score": repo_name_score,
            "description_score": description_score,
            "topics_score": topics_score,
            "readme_score": readme_score,
            "matched_keywords": all_matched,
        }

    def classify_keywords(
        self,
        title: str,
        description: Optional[str] = None,
        readme: Optional[str] = None,
        topics: Optional[List[str]] = None,
        homepage: Optional[str] = None,
    ) -> Tuple[float, List[str]]:
        """
        Calculates backward-compatible keyword intelligence score (0-100) and matched terms.

        Returns:
            Tuple of (keyword_score, list_of_matched_keywords)
        """
        field_analysis = self.analyze_field_scores(
            title=title,
            description=description,
            readme=readme,
            topics=topics,
            homepage=homepage,
        )
        matched = field_analysis["matched_keywords"]

        if not matched:
            return 0.0, []

        # Legacy score mapping: 25 pts per keyword up to 100 max
        score = min(100.0, len(matched) * 25.0)
        return score, matched
