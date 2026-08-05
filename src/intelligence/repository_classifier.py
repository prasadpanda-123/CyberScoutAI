"""
GitHub Repository Quality Classifier Module for CyberScout AI.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple
from src.intelligence.language_filter import LanguageFilter
from src.intelligence.topic_analyzer import TopicAnalyzer


class RepositoryClassifier:
    """
    Specialized classifier for GitHub repositories using topics, primary language,
    stars, forks, watchers, freshness, and metadata.
    """

    def __init__(
        self,
        topic_analyzer: Optional[TopicAnalyzer] = None,
        language_filter: Optional[LanguageFilter] = None,
    ):
        self.topic_analyzer = topic_analyzer or TopicAnalyzer()
        self.language_filter = language_filter or LanguageFilter()

    def calculate_popularity_score(self, raw_data: Dict[str, Any]) -> float:
        """
        Calculates Task 5 Popularity Score (0 to 10 points) using stars, forks, watchers, and contributors.
        """
        stars = int(raw_data.get("stargazers_count") or raw_data.get("stars") or 0)
        forks = int(raw_data.get("forks_count") or raw_data.get("forks") or 0)
        watchers = int(raw_data.get("watchers_count") or raw_data.get("watchers") or 0)
        contributors = int(raw_data.get("contributors_count") or raw_data.get("contributors") or 0)

        if stars >= 500 or forks >= 100 or contributors >= 20:
            return 10.0
        elif stars >= 100 or forks >= 20 or contributors >= 10:
            return 8.0
        elif stars >= 20 or forks >= 5 or watchers >= 10:
            return 6.0
        elif stars >= 5 or forks >= 1:
            return 4.0
        elif stars > 0 or forks > 0:
            return 2.0
        return 0.0

    def calculate_freshness_score(self, raw_data: Dict[str, Any]) -> float:
        """
        Calculates Task 6 Freshness Score (0 to 10 points) using activity timestamps and archived status.
        """
        if raw_data.get("archived") is True:
            return 1.0

        date_str = (
            raw_data.get("pushed_at")
            or raw_data.get("updated_at")
            or raw_data.get("last_commit")
            or raw_data.get("last_release")
            or raw_data.get("published_date")
        )

        if not date_str or not isinstance(date_str, str):
            return 5.0  # Neutral baseline when timestamp is omitted

        # Extract year/month from ISO or formatted string (e.g. 2026-08-05T...)
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                days_diff = (now - dt).days

                if days_diff <= 90:
                    return 10.0
                elif days_diff <= 180:
                    return 8.0
                elif days_diff <= 365:
                    return 5.0
                else:
                    return 2.0
            except Exception:
                if year >= 2025:
                    return 9.0
                return 4.0

        return 5.0

    def calculate_language_score(self, language: Optional[str]) -> float:
        """
        Calculates Task 7 Language Relevance Score (0 to 5 points).
        """
        lang_score_100, _ = self.language_filter.evaluate_language(language)
        if lang_score_100 >= 90.0:
            return 5.0
        elif lang_score_100 >= 40.0:
            return 3.0
        else:
            return 0.0

    def classify_repository(self, raw_data: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """
        Classifies GitHub repository metadata.

        Args:
            raw_data: Raw JSON payload or metadata dictionary from GitHub API / collector.

        Returns:
            Tuple of (repo_score, matched_topics, repo_flags)
        """
        topics: List[str] = raw_data.get("topics") or raw_data.get("repository_topics") or []
        language: Optional[str] = raw_data.get("language")
        stargazers_count: int = int(raw_data.get("stargazers_count") or raw_data.get("stars") or 0)
        forks_count: int = int(raw_data.get("forks_count") or raw_data.get("forks") or 0)

        flags: List[str] = []
        topic_score, matched_topics, has_sec_topic = self.topic_analyzer.analyze_topics(topics)
        lang_score, lang_flag = self.language_filter.evaluate_language(language)

        if lang_flag:
            flags.append(lang_flag)

        if not has_sec_topic and topics:
            flags.append("NO_SECURITY_TOPICS")

        # Social proof credibility boost (stars & forks)
        credibility_boost = 0.0
        if stargazers_count >= 100 or forks_count >= 20:
            credibility_boost = 20.0
            flags.append("POPULAR_REPOSITORY")
        elif stargazers_count >= 10:
            credibility_boost = 10.0

        composite_score = min(100.0, (topic_score * 0.5) + (lang_score * 0.3) + credibility_boost)
        return composite_score, matched_topics, flags
