"""
Unit Tests for ConfidenceScoreCalculator (Phase 11.5).
"""

import pytest
from src.intelligence.confidence_score import ConfidenceScoreCalculator


class TestConfidenceScore:
    """Tests for Stage 9 composite confidence score calculation."""

    def test_high_confidence_all_strong(self):
        calc = ConfidenceScoreCalculator()
        score = calc.compute_confidence(
            keyword_score=100.0,
            topic_score=100.0,
            language_score=100.0,
            relevance_score=100.0,
            source_id="hackernews_rss",
            quality_flags=[],
        )
        assert score >= 90.0

    def test_low_confidence_no_keywords(self):
        calc = ConfidenceScoreCalculator()
        score = calc.compute_confidence(
            keyword_score=0.0,
            topic_score=0.0,
            language_score=50.0,
            relevance_score=0.0,
            source_id="unknown_source",
            quality_flags=["NO_SECURITY_TOPICS"],
        )
        assert score < 60.0

    def test_penalty_for_penalized_language(self):
        calc = ConfidenceScoreCalculator()
        base = calc.compute_confidence(
            keyword_score=50.0,
            topic_score=50.0,
            language_score=50.0,
            relevance_score=50.0,
            source_id="test",
            quality_flags=[],
        )
        penalized = calc.compute_confidence(
            keyword_score=50.0,
            topic_score=50.0,
            language_score=50.0,
            relevance_score=50.0,
            source_id="test",
            quality_flags=["PENALIZED_LANGUAGE"],
        )
        assert penalized < base

    def test_trusted_source_boost(self):
        calc = ConfidenceScoreCalculator()
        generic = calc.compute_confidence(
            keyword_score=30.0,
            topic_score=30.0,
            language_score=50.0,
            relevance_score=30.0,
            source_id="random_unknown",
            quality_flags=[],
        )
        trusted = calc.compute_confidence(
            keyword_score=30.0,
            topic_score=30.0,
            language_score=50.0,
            relevance_score=30.0,
            source_id="cisa_alerts",
            quality_flags=[],
        )
        assert trusted > generic

    def test_score_capped_at_100(self):
        calc = ConfidenceScoreCalculator()
        score = calc.compute_confidence(
            keyword_score=200.0,
            topic_score=200.0,
            language_score=200.0,
            relevance_score=200.0,
            source_id="cisa_alerts",
            quality_flags=[],
        )
        assert score <= 100.0

    def test_score_never_negative(self):
        calc = ConfidenceScoreCalculator()
        score = calc.compute_confidence(
            keyword_score=0.0,
            topic_score=0.0,
            language_score=0.0,
            relevance_score=0.0,
            source_id="unknown",
            quality_flags=["PENALIZED_LANGUAGE", "NO_SECURITY_TOPICS", "UNSUPPORTED_LANGUAGE"],
        )
        assert score >= 0.0
