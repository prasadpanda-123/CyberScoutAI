"""
Stage 2: Repository Topic Analyzer Module for CyberScout AI.
"""

from typing import List, Optional, Tuple, Set
from src.intelligence.quality_rules import QualityRules


class TopicAnalyzer:
    """
    Evaluates repository topics against approved cybersecurity topic taxonomies.
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def analyze_topics(self, topics: List[str]) -> Tuple[float, List[str], bool]:
        """
        Analyzes topics list.

        Args:
            topics: List of topic strings (e.g. ['security', 'ctf', 'owasp']).

        Returns:
            Tuple of (topic_score, matched_approved_topics, has_security_topic)
        """
        if not topics:
            return 0.0, [], True  # Missing topic metadata does not cause immediate hard rejection for non-GitHub items

        cleaned_topics = {str(t).lower().strip() for t in topics if t}
        approved = set(self.rules.approved_topics)

        matched = cleaned_topics.intersection(approved)

        if not matched:
            # Check if any topic contains approved keywords as substrings
            for top in cleaned_topics:
                for app in approved:
                    if app in top or top in app:
                        matched.add(top)

        if not matched:
            return 0.0, [], False

        # Calculate topic score based on matches
        score = min(100.0, len(matched) * 35.0)
        return score, list(matched), True
