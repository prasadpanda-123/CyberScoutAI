"""
Integration Tests for Quality Intelligence Pipeline (Phase 11.5).
"""

import pytest
from src.intelligence.quality_engine import QualityEngine
from src.intelligence.quality_metrics import QualityMetrics
from src.models.opportunity import Opportunity


def _make_opp(**kwargs):
    """Helper factory."""
    defaults = {
        "title": "Integration Test Opportunity",
        "url": "https://example.com/integration-test",
        "source_id": "test_source",
        "description": "A cybersecurity opportunity for integration testing purposes.",
        "category": "other",
    }
    defaults.update(kwargs)
    return Opportunity(**defaults)


class TestQualityPipelineIntegration:
    """End-to-end pipeline integration tests."""

    def test_full_pipeline_mixed_batch(self):
        """Tests a mixed batch with legitimate + spam + duplicate items."""
        engine = QualityEngine()

        opps = [
            # Should ACCEPT: valid cybersecurity internship
            _make_opp(
                title="Cybersecurity Internship at SecureCorp",
                url="https://securecorp.com/internship",
                description="Join our SOC team and learn about SIEM, IDS, incident response, and vulnerability assessment.",
                raw_data={"topics": ["security", "soc"], "language": "Python"},
            ),
            # Should ACCEPT: valid CTF event
            _make_opp(
                title="HackTheBox University CTF 2026",
                url="https://hackthebox.com/ctf-2026",
                source_id="hackthebox_academy",
                description="Annual CTF competition covering reverse engineering, forensics, cryptography, and web exploitation.",
                raw_data={"topics": ["ctf", "security"], "language": "Python"},
            ),
            # Should REJECT: IPTV playlist
            _make_opp(
                title="Free IPTV M3U Playlist",
                url="https://github.com/user/iptv-list",
                description="#EXTM3U\n#EXTINF:-1,Sports Channel\nhttp://stream.example.com/1",
                source_id="github_search",
                raw_data={"topics": ["iptv", "m3u"], "language": "HTML"},
            ),
            # Should REJECT: movie collection
            _make_opp(
                title="Ultimate Free Movies Repository",
                url="https://github.com/user/movies",
                description="Curated list of free movies, anime, music collections, and streaming channels.",
                source_id="github_search",
            ),
            # Should REJECT: duplicate of first item
            _make_opp(
                title="Cybersecurity Internship at SecureCorp",
                url="https://securecorp.com/internship",
                description="Duplicate entry.",
            ),
        ]

        results = engine.evaluate_batch(opps)

        assert len(results) == 5

        accepted = [o for o in results if not o.is_rejected]
        rejected = [o for o in results if o.is_rejected]

        assert len(accepted) == 2, f"Expected 2 accepted, got {len(accepted)}: {[o.title for o in accepted]}"
        assert len(rejected) == 3, f"Expected 3 rejected, got {len(rejected)}: {[(o.title, o.rejection_reason) for o in rejected]}"

        # Verify metrics
        assert engine.metrics.evaluated_count == 5
        assert engine.metrics.accepted_count == 2
        assert engine.metrics.rejected_count == 3

    def test_all_legitimate_batch(self):
        """Tests a batch with only legitimate cybersecurity items."""
        engine = QualityEngine()

        opps = [
            _make_opp(
                title=f"Security Tool #{i} - OWASP Scanner",
                url=f"https://example.com/security-tool-{i}",
                description="A vulnerability scanner that checks for SQL injection, XSS, and CSRF vulnerabilities.",
            )
            for i in range(3)
        ]

        accepted = engine.filter_accepted(opps)
        assert len(accepted) == 3

    def test_all_spam_batch(self):
        """Tests a batch with only spam/blacklisted items."""
        engine = QualityEngine()

        opps = [
            _make_opp(
                title="Free IPTV Channels",
                url="https://example.com/iptv-1",
                description="#EXTM3U iptv playlist channels",
            ),
            _make_opp(
                title="Torrent Movie Downloads",
                url="https://example.com/torrent-1",
                description="Download free movies via torrent files.",
            ),
            _make_opp(
                title="Anime Streaming Collection",
                url="https://example.com/anime-1",
                description="Watch free anime episodes online streaming.",
            ),
        ]

        accepted = engine.filter_accepted(opps)
        assert len(accepted) == 0

    def test_quality_flags_assigned(self):
        """Tests that quality flags are correctly assigned to accepted items."""
        engine = QualityEngine()
        opp = _make_opp(
            title="Malware Analysis Lab with YARA Rules",
            url="https://example.com/malware-lab",
            description="Learn malware analysis, reverse engineering, and YARA rule writing for threat detection.",
            raw_data={"topics": ["malware", "security"], "language": "Python"},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected
        assert result.confidence_score > 0
        assert result.keyword_score > 0

    def test_confidence_threshold_boundary(self):
        """Tests items near the confidence threshold boundary."""
        engine = QualityEngine()
        # Item with minimal security keywords but from a trusted source
        opp = _make_opp(
            title="Weekly Security Newsletter",
            url="https://krebsonsecurity.com/newsletter",
            source_id="krebsonsecurity_rss",
            description="Latest security news, vulnerability disclosures, and threat intelligence updates from Krebs.",
        )
        result = engine.evaluate_opportunity(opp)
        # Trusted source should boost above threshold
        assert not result.is_rejected
