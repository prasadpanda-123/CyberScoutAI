"""
Stage 9: Confidence Score Engine for CyberScout AI.
"""

from typing import Dict, List, Optional, Tuple
from src.intelligence.quality_rules import QualityRules


class ConfidenceScoreCalculator:
    """
    Computes Stage 9 composite confidence score (0-100) based on weighted inputs,
    component breakdowns, penalties, and credibility multipliers.
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def compute_weighted_confidence(
        self,
        repo_name_score: float,
        description_score: float,
        topics_score: float,
        readme_score: float,
        popularity_score: float,
        freshness_score: float,
        language_score: float,
        source_id: str = "",
        quality_flags: Optional[List[str]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculates Task 4 weighted 100-point confidence score:
        - Repo Name: 20 pts
        - Description: 20 pts
        - Topics: 20 pts
        - README: 15 pts
        - Popularity: 10 pts
        - Freshness: 10 pts
        - Language: 5 pts
        Total Max: 100 pts.

        Returns:
            Tuple of (final_confidence_score, breakdown_dict)
        """
        flags = quality_flags or []

        # Raw sum of all 7 weighted components
        component_sum = (
            repo_name_score
            + description_score
            + topics_score
            + readme_score
            + popularity_score
            + freshness_score
            + language_score
        )

        # Source credibility boost for official trusted cybersecurity sources
        credibility_boost = 0.0
        official_sources = [
            "hackernews_rss", "bleepingcomputer_rss", "krebsonsecurity_rss",
            "darkreading_rss", "portswigger_feed", "portswigger_academy", "tryhackme",
            "tryhackme_rss", "hackthebox", "hackthebox_rss", "ctftime", "cisa_alerts",
            "sans_isc", "owasp", "owasp_official", "picoctf", "picoctf_official",
            "cve_mitre", "mitre_attack", "gsoc_official", "microsoft_jobs", "github_sec"
        ]
        if any(src in source_id.lower() for src in official_sources):
            credibility_boost = 15.0

        raw_score = component_sum + credibility_boost

        # Quality flag penalties
        penalty = 0.0
        if "PENALIZED_LANGUAGE" in flags:
            penalty += 25.0
        if "UNSUPPORTED_LANGUAGE" in flags:
            penalty += 5.0
        if "BLACKLISTED" in flags or "SPAM_STRUCTURE" in flags:
            penalty += 100.0

        final_score = max(0.0, min(100.0, raw_score - penalty))
        final_score = round(final_score, 1)

        breakdown = {
            "repo_name_score": round(repo_name_score, 1),
            "description_score": round(description_score, 1),
            "topics_score": round(topics_score, 1),
            "readme_score": round(readme_score, 1),
            "popularity_score": round(popularity_score, 1),
            "freshness_score": round(freshness_score, 1),
            "language_score": round(language_score, 1),
            "credibility_boost": round(credibility_boost, 1),
            "penalty": round(penalty, 1),
            "final_confidence": final_score,
        }

        return final_score, breakdown

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
        Legacy backward-compatible confidence calculation method.
        """
        w = self.rules.weights
        kw_w = w.get("keyword_weight", 0.35)
        top_w = w.get("topic_weight", 0.25)
        lang_w = w.get("language_weight", 0.15)
        rel_w = w.get("relevance_weight", 0.15)
        cred_w = w.get("source_credibility_weight", 0.10)

        credibility = 50.0
        official_sources = [
            "hackernews_rss", "bleepingcomputer_rss", "krebsonsecurity_rss",
            "darkreading_rss", "portswigger_academy", "tryhackme",
            "hackthebox_academy", "ctftime", "cisa_alerts", "sans_isc", "owasp"
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

        if keyword_score >= 50.0 and base_score < 65.0:
            base_score = max(base_score, 65.0)

        penalty = 0.0
        if "PENALIZED_LANGUAGE" in quality_flags:
            penalty += 30.0
        if "NO_SECURITY_TOPICS" in quality_flags:
            penalty += 20.0
        if "UNSUPPORTED_LANGUAGE" in quality_flags:
            penalty += 10.0

        final_score = max(0.0, min(100.0, base_score - penalty))
        return round(final_score, 1)
