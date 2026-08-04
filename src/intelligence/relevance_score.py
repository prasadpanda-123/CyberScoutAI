"""
Cybersecurity Domain Relevance Score Module for CyberScout AI.
"""

from typing import Dict, List, Optional
from src.intelligence.quality_rules import QualityRules


class RelevanceScoreCalculator:
    """
    Computes overall cybersecurity domain relevance rating (0-100).
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def calculate_relevance(
        self,
        category: str,
        keyword_score: float,
        topic_score: float,
        repo_score: float,
        source_id: str,
    ) -> float:
        """
        Calculates domain relevance rating.

        Returns:
            Float score between 0.0 and 100.0
        """
        # Trusted core cybersecurity providers receive a baseline boost
        baseline = 0.0
        trusted_sources = [
            "hackernews_rss", "bleepingcomputer_rss", "krebsonsecurity_rss",
            "darkreading_rss", "portswigger_academy", "tryhackme",
            "hackthebox_academy", "ctftime", "cisa_alerts", "sans_isc"
        ]
        if any(ts in source_id.lower() for ts in trusted_sources):
            baseline = 60.0

        # Weighted calculation
        raw = (keyword_score * 0.40) + (topic_score * 0.30) + (repo_score * 0.30) + baseline
        return min(100.0, max(0.0, raw))
