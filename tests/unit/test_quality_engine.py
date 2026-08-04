"""
Unit Tests for Quality Intelligence Engine (Phase 11.5).
"""

import pytest
from unittest.mock import patch, MagicMock
from src.intelligence.quality_engine import QualityEngine
from src.intelligence.quality_rules import QualityRules
from src.intelligence.quality_metrics import QualityMetrics
from src.models.opportunity import Opportunity


def _make_opp(**kwargs):
    """Helper factory to create test Opportunity instances."""
    defaults = {
        "title": "Test Cybersecurity Opportunity",
        "url": "https://example.com/test-opp",
        "source_id": "test_source",
        "description": "A detailed description of a cybersecurity opportunity for testing purposes.",
        "category": "internship",
    }
    defaults.update(kwargs)
    return Opportunity(**defaults)


class TestQualityEngineAcceptance:
    """Tests for opportunities that should be ACCEPTED."""

    def test_accept_owasp_internship(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="OWASP Top 10 Security Internship 2026",
            description="Learn about SQL injection, XSS, CSRF, and authentication vulnerabilities in this internship.",
            raw_data={"topics": ["security", "owasp"], "language": "Python"},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected, f"Expected acceptance, got rejection: {result.rejection_reason}"
        assert result.confidence_score >= 60.0

    def test_accept_ctf_event(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="PicoCTF 2026 Competition",
            url="https://ctftime.org/event/123",
            description="A beginner-friendly CTF competition covering forensics, reverse engineering, and cryptography.",
            source_id="ctftime",
            raw_data={"topics": ["ctf", "security"]},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_cve_advisory(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="CVE-2026-12345 Critical Remote Code Execution",
            url="https://cisa.gov/advisory/12345",
            source_id="cisa_alerts",
            description="Critical vulnerability affecting web servers.",
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_tryhackme_course(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="TryHackMe SOC Analyst Path",
            url="https://tryhackme.com/path/soc-analyst",
            source_id="tryhackme",
            description="Complete SOC analyst training path with SIEM, incident response, and log analysis modules.",
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected


class TestQualityEngineRejection:
    """Tests for opportunities that should be REJECTED."""

    def test_reject_iptv_playlist(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="Free IPTV Channels Worldwide",
            url="https://github.com/user/iptv-channels",
            description="#EXTM3U\n#EXTINF:-1,Channel 1\nhttp://stream.example.com/1",
            source_id="github_search",
            raw_data={"topics": ["iptv", "m3u"], "language": "HTML"},
        )
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected
        assert "PLAYLIST" in result.rejection_reason or "BLACKLIST" in result.rejection_reason

    def test_reject_movie_collection(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="Best Free Movies and TV Shows Collection",
            url="https://github.com/user/free-movies",
            description="A curated list of free movies, anime, music, and streaming channels.",
            source_id="github_search",
            raw_data={"topics": ["movies", "anime"], "language": "Markdown"},
        )
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected

    def test_reject_torrent_repository(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="Torrent Search Engine",
            url="https://github.com/user/torrent-search",
            description="Download torrents for free movies, music, and software.",
            source_id="github_search",
        )
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected

    def test_reject_empty_title(self):
        engine = QualityEngine()
        opp = _make_opp(title="", description="Some description.")
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected
        assert result.rejection_reason == "INVALID_CONTENT"

    def test_reject_invalid_url(self):
        engine = QualityEngine()
        opp = _make_opp(url="not-a-valid-url")
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected
        assert result.rejection_reason == "INVALID_CONTENT"


class TestQualityEngineDuplicates:
    """Tests for duplicate detection."""

    def test_reject_duplicate_url(self):
        engine = QualityEngine()
        opp1 = _make_opp(title="First Opportunity", url="https://example.com/dupe-test")
        opp2 = _make_opp(title="Second Opportunity", url="https://example.com/dupe-test")
        engine.evaluate_opportunity(opp1)
        result = engine.evaluate_opportunity(opp2)
        assert result.is_rejected
        assert result.rejection_reason == "DUPLICATE"

    def test_reject_duplicate_title(self):
        engine = QualityEngine()
        opp1 = _make_opp(title="Same Title Opportunity", url="https://example.com/unique1")
        opp2 = _make_opp(title="Same Title Opportunity", url="https://example.com/unique2")
        engine.evaluate_opportunity(opp1)
        result = engine.evaluate_opportunity(opp2)
        assert result.is_rejected
        assert result.rejection_reason == "DUPLICATE"


class TestQualityEngineBatch:
    """Tests for batch evaluation."""

    def test_batch_evaluation(self):
        engine = QualityEngine()
        opps = [
            _make_opp(
                title=f"Security Tool #{i}",
                url=f"https://example.com/tool-{i}",
                description="A cybersecurity vulnerability scanning tool with OWASP support.",
            )
            for i in range(5)
        ]
        results = engine.evaluate_batch(opps)
        assert len(results) == 5

    def test_filter_accepted(self):
        engine = QualityEngine()
        opps = [
            _make_opp(
                title="Valid Security Tool",
                url="https://example.com/valid",
                description="OWASP vulnerability scanner with CVE detection capabilities.",
            ),
            _make_opp(
                title="IPTV Playlist Collection",
                url="https://example.com/iptv",
                description="#EXTM3U free iptv channels worldwide",
            ),
        ]
        accepted = engine.filter_accepted(opps)
        assert len(accepted) == 1
        assert accepted[0].title == "Valid Security Tool"


class TestQualityMetrics:
    """Tests for metrics tracking."""

    def test_metrics_recording(self):
        metrics = QualityMetrics()
        metrics.record_evaluation(accepted=True, confidence_score=85.0, matched_keywords=["OWASP", "CVE"])
        metrics.record_evaluation(accepted=False, confidence_score=20.0, rejection_reason="BLACKLIST_KEYWORD", is_spam=True)

        assert metrics.evaluated_count == 2
        assert metrics.accepted_count == 1
        assert metrics.rejected_count == 1
        assert metrics.spam_attempts_blocked == 1
        assert metrics.acceptance_rate == 50.0

    def test_metrics_to_dict(self):
        metrics = QualityMetrics()
        metrics.record_evaluation(accepted=True, confidence_score=95.0)
        d = metrics.to_dict()
        assert "evaluated_count" in d
        assert "confidence_distribution" in d
        assert d["evaluated_count"] == 1
