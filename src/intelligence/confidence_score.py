"""
Stage 9: Confidence Score Engine for CyberScout AI.
"""

from typing import List, Optional
from src.intelligence.quality_rules import QualityRules


class ConfidenceScoreCalculator:
    """
    Computes Stage 9 composite confidence score (0-100) based on weighted inputs,
    penalties, and credibility multipliers.
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def compute_confidence(
        self,
        keyword_score: float,
        topic_score: float,
        language_score: float,
        relevance_score: float,
        source_id: str,
        quality_flags: List[str],
    ) -> float:
        """
        Computes composite confidence score (0-100).

        Returns:
            Normalized float between 0.0 and 100.0
        """
        w = self.rules.weights
        kw_w = w.get("keyword_weight", 0.35)
        top_w = w.get("topic_weight", 0.25)
        lang_w = w.get("language_weight", 0.15)
        rel_w = w.get("relevance_weight", 0.15)
        cred_w = w.get("source_credibility_weight", 0.10)

        # Baseline credibility score from source
        credibility = 50.0
        official_sources = [
            "hackernews_rss", "bleepingcomputer_rss", "krebsonsecurity_rss",
            "darkreading_rss", "portswigger_academy", "tryhackme",
            "hackthebox_academy", "ctftime", "cisa_alerts", "sans_isc"
        ]
        if any(src in source_id.lower() for src in official_sources):
            credibility = 95.0

        base_score = (
            (keyword_score * kw_w) +
            (topic_score * top_w) +
            (language_score * lang_w) +
            (relevance_score * rel_w) +
            (credibility * cred_w)
        )

        # Keyword-driven confidence floor: if strong keyword matches exist,
        # the item is likely legitimate cybersecurity content even without
        # topic metadata (e.g., CVE advisories, RSS items, non-GitHub sources).
        if keyword_score >= 50.0 and base_score < 65.0:
            base_score = max(base_score, 65.0)

        # Apply penalties for quality flags
        penalty = 0.0
        if "PENALIZED_LANGUAGE" in quality_flags:
            penalty += 30.0
        if "NO_SECURITY_TOPICS" in quality_flags:
            penalty += 20.0
        if "UNSUPPORTED_LANGUAGE" in quality_flags:
            penalty += 10.0

        final_score = max(0.0, min(100.0, base_score - penalty))
        return round(final_score, 1)
