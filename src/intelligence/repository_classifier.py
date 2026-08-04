"""
GitHub Repository Quality Classifier Module for CyberScout AI.
"""

from typing import Any, Dict, List, Optional, Tuple
from src.intelligence.language_filter import LanguageFilter
from src.intelligence.topic_analyzer import TopicAnalyzer


class RepositoryClassifier:
    """
    Specialized classifier for GitHub repositories using topics, primary language,
    stars, forks, and metadata.
    """

    def __init__(
        self,
        topic_analyzer: Optional[TopicAnalyzer] = None,
        language_filter: Optional[LanguageFilter] = None,
    ):
        self.topic_analyzer = topic_analyzer or TopicAnalyzer()
        self.language_filter = language_filter or LanguageFilter()

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
