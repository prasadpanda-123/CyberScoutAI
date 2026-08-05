"""
Master Quality Intelligence Engine for CyberScout AI (Phase 11.5).

Orchestrates the weighted 7-component evaluation pipeline for all ingested opportunities.
"""

from typing import Dict, List, Optional, Set, Tuple

from src.core.logging import get_logger
from src.intelligence.confidence_score import ConfidenceScoreCalculator
from src.intelligence.content_validator import ContentValidator
from src.intelligence.keyword_classifier import KeywordClassifier
from src.intelligence.language_filter import LanguageFilter
from src.intelligence.quality_metrics import QualityMetrics
from src.intelligence.quality_rules import QualityRules
from src.intelligence.relevance_score import RelevanceScoreCalculator
from src.intelligence.repository_classifier import RepositoryClassifier
from src.intelligence.spam_detector import SpamDetector
from src.intelligence.topic_analyzer import TopicAnalyzer
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


class QualityEngine:
    """
    Central Quality Intelligence Engine inspecting every opportunity before storage,
    ranking, or email notification.
    """

    def __init__(
        self,
        rules: Optional[QualityRules] = None,
        metrics: Optional[QualityMetrics] = None,
    ):
        self.rules = rules or QualityRules()
        self.metrics = metrics or QualityMetrics()

        self.content_validator = ContentValidator()
        self.topic_analyzer = TopicAnalyzer(rules=self.rules)
        self.language_filter = LanguageFilter(rules=self.rules)
        self.keyword_classifier = KeywordClassifier(rules=self.rules)
        self.spam_detector = SpamDetector(rules=self.rules)
        self.repo_classifier = RepositoryClassifier(
            topic_analyzer=self.topic_analyzer,
            language_filter=self.language_filter,
        )
        self.relevance_calculator = RelevanceScoreCalculator(rules=self.rules)
        self.confidence_calculator = ConfidenceScoreCalculator(rules=self.rules)

        self._seen_urls: Set[str] = set()
        self._seen_titles: Set[str] = set()

    def evaluate_opportunity(self, opportunity: Opportunity) -> Opportunity:
        """
        Runs an Opportunity model through the quality evaluation pipeline.
        Attaches quality fields, score breakdown, and decision metadata.

        Args:
            opportunity: Target Opportunity model instance.

        Returns:
            Evaluated Opportunity model.
        """
        title = opportunity.title or ""
        url = opportunity.url or ""
        description = opportunity.description or ""
        source_id = opportunity.source_id or ""
        category = opportunity.category or "other"

        raw_data = getattr(opportunity, "raw_data", {}) or {}
        if not isinstance(raw_data, dict):
            raw_data = {}

        readme = raw_data.get("readme") or raw_data.get("body") or ""
        topics = raw_data.get("topics") or raw_data.get("repository_topics") or []
        homepage = raw_data.get("homepage") or ""
        language = raw_data.get("language")
        license_name = raw_data.get("license")
        if isinstance(license_name, dict):
            license_name = license_name.get("name") or license_name.get("key") or ""
        owner_type = raw_data.get("owner_type")
        if not owner_type and isinstance(raw_data.get("owner"), dict):
            owner_type = raw_data.get("owner", {}).get("type")

        quality_flags: List[str] = []

        # ---------------------------------------------------------------------
        # STAGE 1: Basic Content & Syntax Validation
        # ---------------------------------------------------------------------
        is_val, val_reason, val_msg = self.content_validator.validate(title, url, description)
        if not is_val:
            return self._reject(opportunity, val_reason, val_msg, flags=["SYNTAX_ERROR"])

        # ---------------------------------------------------------------------
        # STAGE 5: Blacklist Engine (Instant Discard)
        # ---------------------------------------------------------------------
        combined_text = f"{title} {description} {readme} {' '.join(topics)} {homepage}"
        is_bl, bl_match = self.spam_detector.check_blacklist(combined_text)
        if is_bl:
            reason = "PLAYLIST_DETECTED" if ("#extm3u" in bl_match.lower() or "iptv" in bl_match.lower()) else "BLACKLIST_KEYWORD"
            return self._reject(opportunity, reason, f"Matched blacklisted term: '{bl_match}'", flags=["BLACKLISTED"])

        # ---------------------------------------------------------------------
        # STAGE 6: README & Structure Spam Analyzer
        # ---------------------------------------------------------------------
        is_spam, spam_score, spam_msg = self.spam_detector.analyze_readme_structure(readme)
        if is_spam:
            return self._reject(opportunity, "SPAM", spam_msg, flags=["SPAM_STRUCTURE"], spam_score=spam_score * 100.0)

        # ---------------------------------------------------------------------
        # STAGE 8: Duplicate Detection
        # ---------------------------------------------------------------------
        norm_url = url.lower().strip().rstrip("/")
        norm_title = title.lower().strip()
        if norm_url in self._seen_urls or norm_title in self._seen_titles:
            return self._reject(opportunity, "DUPLICATE", f"Duplicate title or URL: '{url}'", flags=["DUPLICATE_ITEM"])
        self._seen_urls.add(norm_url)
        self._seen_titles.add(norm_title)

        # ---------------------------------------------------------------------
        # Metadata Analysis & 7-Component Weighted Scoring (Tasks 2, 4, 5, 6, 7)
        # ---------------------------------------------------------------------
        field_analysis = self.keyword_classifier.analyze_field_scores(
            title=title,
            description=description,
            readme=readme,
            topics=topics,
            homepage=homepage,
            url=url,
            license_name=str(license_name) if license_name else None,
            owner_type=str(owner_type) if owner_type else None,
        )

        repo_name_score = field_analysis["repo_name_score"]
        description_score = field_analysis["description_score"]
        topics_score = field_analysis["topics_score"]
        readme_score = field_analysis["readme_score"]
        matched_keywords = field_analysis["matched_keywords"]

        popularity_score = self.repo_classifier.calculate_popularity_score(raw_data)
        freshness_score = self.repo_classifier.calculate_freshness_score(raw_data)
        language_score = self.repo_classifier.calculate_language_score(language)

        _, lang_flag = self.language_filter.evaluate_language(language)
        if lang_flag:
            quality_flags.append(lang_flag)

        topic_score, matched_topics, has_sec_topic = self.topic_analyzer.analyze_topics(topics)
        if not has_sec_topic and topics:
            quality_flags.append("NO_SECURITY_TOPICS")

        # Compute Task 4 & Task 8 Composite Confidence Score (0 - 100)
        confidence_score, breakdown = self.confidence_calculator.compute_weighted_confidence(
            repo_name_score=repo_name_score,
            description_score=description_score,
            topics_score=topics_score,
            readme_score=readme_score,
            popularity_score=popularity_score,
            freshness_score=freshness_score,
            language_score=language_score,
            source_id=source_id,
            quality_flags=quality_flags,
        )

        # Compute legacy relevance & quality scores for backward compatibility
        repo_score, _, repo_flags = self.repo_classifier.classify_repository(raw_data)
        quality_flags.extend(repo_flags)
        relevance_score = self.relevance_calculator.calculate_relevance(
            category=category,
            keyword_score=repo_name_score + description_score,
            topic_score=topic_score,
            repo_score=repo_score,
            source_id=source_id,
        )

        # ---------------------------------------------------------------------
        # Decision Matrix & Threshold Checking (Task 9)
        # ---------------------------------------------------------------------
        decision = "REJECTED"
        reason = "LOW_CONFIDENCE"

        if confidence_score >= self.rules.accept_medium_threshold:  # 60.0+
            decision = "ACCEPTED"
            reason = "Repository contains multiple cybersecurity indicators with strong community adoption."
        elif confidence_score >= self.rules.needs_review_threshold:  # 40.0 - 59.0
            decision = "ACCEPTED"
            reason = "Moderate cybersecurity confidence score; flagged for optional review."
            quality_flags.append("NEEDS_REVIEW")
        else:
            reason = f"Confidence score {confidence_score:.1f} is below minimum threshold {self.rules.needs_review_threshold:.1f}"

        # ---------------------------------------------------------------------
        # Task 10: Formatted Diagnostic Logging
        # ---------------------------------------------------------------------
        diag_log = (
            "\n------------------------------------------------\n"
            f"Repository:\n{title}\n\n"
            f"Keyword Score:\n{int(repo_name_score)}\n\n"
            f"Description Score:\n{int(description_score)}\n\n"
            f"Topics Score:\n{int(topics_score)}\n\n"
            f"README Score:\n{int(readme_score)}\n\n"
            f"Popularity:\n{int(popularity_score)}\n\n"
            f"Freshness:\n{int(freshness_score)}\n\n"
            f"Language:\n{int(language_score)}\n\n"
            f"Final Confidence:\n{int(confidence_score)}\n\n"
            f"Decision:\n{decision}\n\n"
            f"Reason:\n{reason}\n"
            "------------------------------------------------"
        )
        logger.info(diag_log)

        # If decision is rejection, return rejected model
        if decision == "REJECTED":
            return self._reject(
                opportunity,
                "LOW_CONFIDENCE",
                reason,
                flags=quality_flags,
                confidence_score=confidence_score,
                keyword_score=repo_name_score + description_score,
                topic_score=topics_score,
                breakdown=breakdown,
            )

        # ---------------------------------------------------------------------
        # Task 11: Accept & Attach Score Breakdown Diagnostics
        # ---------------------------------------------------------------------
        breakdown["decision"] = decision
        breakdown["reason"] = reason

        opportunity.confidence_score = confidence_score
        opportunity.quality_score = max(confidence_score, relevance_score)
        opportunity.is_rejected = False
        opportunity.rejection_reason = ""
        opportunity.quality_flags = ",".join(sorted(list(set(quality_flags))))
        opportunity.topic_score = topics_score
        opportunity.keyword_score = repo_name_score + description_score
        opportunity.spam_score = 0.0
        opportunity.score_breakdown = breakdown

        self.metrics.record_evaluation(
            accepted=True,
            confidence_score=confidence_score,
            matched_keywords=matched_keywords,
            matched_topics=matched_topics,
        )

        return opportunity

    def evaluate_batch(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """
        Evaluates a batch of Opportunity instances.

        Args:
            opportunities: List of Opportunity instances.

        Returns:
            List of evaluated Opportunity instances.
        """
        results: List[Opportunity] = []
        for opp in opportunities:
            eval_opp = self.evaluate_opportunity(opp)
            results.append(eval_opp)
        return results

    def filter_accepted(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """
        Filters a list of Opportunity instances, returning ONLY accepted ones.

        Args:
            opportunities: List of Opportunity instances.

        Returns:
            List of accepted non-rejected Opportunity instances.
        """
        evaluated = self.evaluate_batch(opportunities)
        return [opp for opp in evaluated if not opp.is_rejected]

    def calculate_quality_score(self, opportunity: Opportunity) -> float:
        """
        Backward-compatible quality score accessor used by RankingEngine & ConfidenceEngine.
        """
        title = opportunity.title or ""
        description = opportunity.description or ""
        raw_data = getattr(opportunity, "raw_data", {}) or {}
        if not isinstance(raw_data, dict):
            raw_data = {}

        readme = raw_data.get("readme") or raw_data.get("body") or ""
        topics = raw_data.get("topics") or []
        homepage = raw_data.get("homepage") or ""

        kw_score, _ = self.keyword_classifier.classify_keywords(
            title=title,
            description=description,
            readme=readme,
            topics=topics,
            homepage=homepage,
        )
        return kw_score

    def _reject(
        self,
        opportunity: Opportunity,
        reason: str,
        message: str,
        flags: Optional[List[str]] = None,
        confidence_score: float = 0.0,
        keyword_score: float = 0.0,
        topic_score: float = 0.0,
        spam_score: float = 0.0,
        breakdown: Optional[Dict[str, float]] = None,
    ) -> Opportunity:
        """Helper to mark an opportunity as rejected with metadata and diagnostic breakdown."""
        flags = flags or []
        opportunity.confidence_score = confidence_score
        opportunity.quality_score = 0.0
        opportunity.is_rejected = True
        opportunity.rejection_reason = reason
        opportunity.quality_flags = ",".join(sorted(list(set(flags))))
        opportunity.topic_score = topic_score
        opportunity.keyword_score = keyword_score
        opportunity.spam_score = spam_score

        if breakdown:
            breakdown["decision"] = "REJECTED"
            breakdown["reason"] = message
            opportunity.score_breakdown = breakdown

        is_dup = reason == "DUPLICATE"
        is_spm = reason in ["SPAM", "PLAYLIST_DETECTED", "BLACKLIST_KEYWORD"]

        self.metrics.record_evaluation(
            accepted=False,
            confidence_score=confidence_score,
            rejection_reason=reason,
            is_duplicate=is_dup,
            is_spam=is_spm,
        )

        logger.warning(f"QualityEngine REJECTED '{opportunity.title}' [{reason}]: {message}")
        return opportunity
