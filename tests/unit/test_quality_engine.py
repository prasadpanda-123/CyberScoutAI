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
    """Tests for cybersecurity opportunities that MUST be ACCEPTED (Task 13)."""

    def test_accept_security_tools_bl4de(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="bl4de/security-tools",
            url="https://github.com/bl4de/security-tools",
            description="Various security and pentesting scripts, exploits, and audit tools.",
            source_id="github_search",
            raw_data={"topics": ["security-tools", "pentest", "python"], "language": "Python", "stargazers_count": 450},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected, f"bl4de/security-tools rejected: {result.rejection_reason}"
        assert result.confidence_score >= 60.0

    def test_accept_picoctf(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="picoCTF 2026 Repository",
            url="https://github.com/picoCTF/picoCTF",
            description="PicoCTF challenges covering reverse engineering, cryptography, binary exploitation, and forensics.",
            source_id="github_search",
            raw_data={"topics": ["picoctf", "ctf", "security"], "language": "Python", "stargazers_count": 1200},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected
        assert result.confidence_score >= 80.0

    def test_accept_cyberdefenders(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="CyberDefenders Blue Team Artifacts",
            url="https://github.com/CyberDefenders/blue-team-labs",
            description="DFIR exercises and SOC analyst threat hunting practice challenges.",
            source_id="github_search",
            raw_data={"topics": ["cyberdefenders", "blue-team", "dfir"], "language": "Python", "stargazers_count": 350},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_hackthebox(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="HackTheBox Machine Exploitation Writeups",
            url="https://github.com/htb/writeups",
            description="HTB penetration testing walkthroughs covering active directory, kerberos, and privilege escalation.",
            source_id="github_search",
            raw_data={"topics": ["hackthebox", "htb", "pentest"], "language": "Go"},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_ctfd(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="CTFd Platform Core Framework",
            url="https://github.com/CTFd/CTFd",
            description="Capture The Flag framework customizable for security competitions.",
            source_id="github_search",
            raw_data={"topics": ["ctfd", "ctf", "cybersecurity"], "language": "Python", "stargazers_count": 5000},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_owasp_projects(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="OWASP Juice Shop Web Application",
            url="https://github.com/OWASP/juice-shop",
            description="Probably the most modern and sophisticated insecure web application for OWASP vulnerability training.",
            source_id="github_search",
            raw_data={"topics": ["owasp", "web-security", "appsec"], "language": "TypeScript", "stargazers_count": 9000},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_tryhackme(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="TryHackMe Room Automation Scripts",
            url="https://github.com/thm/automation-tools",
            description="TryHackMe THM cybersecurity room deployment tools.",
            source_id="github_search",
            raw_data={"topics": ["tryhackme", "thm", "security"], "language": "Python"},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_blue_team(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="Blue Team SOC Detection Rules",
            url="https://github.com/blueteam/siem-rules",
            description="Sigma and YARA threat hunting rules for blue team SOC operations.",
            source_id="github_search",
            raw_data={"topics": ["blue-team", "siem", "soc"], "language": "Python"},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_red_team(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="Red Team Implant Framework",
            url="https://github.com/redteam/c2-framework",
            description="Adversary emulation and red team pentesting command and control framework.",
            source_id="github_search",
            raw_data={"topics": ["red-team", "pentest", "exploit"], "language": "Go"},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected

    def test_accept_dfir(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="DFIR Memory Analysis Tools",
            url="https://github.com/dfir/volatility-plugins",
            description="Digital forensics and incident response plugins for memory dump analysis.",
            source_id="github_search",
            raw_data={"topics": ["dfir", "digital-forensics", "incident-response"], "language": "Python"},
        )
        result = engine.evaluate_opportunity(opp)
        assert not result.is_rejected


class TestQualityEngineUnrelatedRejection:
    """Tests ensuring non-cybersecurity repositories ARE REJECTED (Task 13)."""

    def test_reject_weather_app(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="React Weather Forecast Dashboard",
            url="https://github.com/user/weather-app",
            description="A simple weather application using OpenWeatherMap API to display daily temperature and humidity.",
            source_id="github_search",
            raw_data={"topics": ["weather", "react", "dashboard"], "language": "JavaScript"},
        )
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected, "Weather app should be rejected"

    def test_reject_flappy_bird_game(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="Flappy Bird Clone in Unity C#",
            url="https://github.com/user/flappy-bird-unity",
            description="2D arcade game clone of Flappy Bird built with Unity engine.",
            source_id="github_search",
            raw_data={"topics": ["gaming", "unity", "gamedev"], "language": "C#"},
        )
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected

    def test_reject_generic_ml_tutorial(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="PyTorch Image Classification Tutorial",
            url="https://github.com/user/pytorch-mnist",
            description="Basic machine learning tutorial classifying MNIST handwritten digits using PyTorch.",
            source_id="github_search",
            raw_data={"topics": ["machine-learning", "pytorch", "deep-learning"], "language": "Python"},
        )
        result = engine.evaluate_opportunity(opp)
        assert result.is_rejected


class TestQualityEngineDiagnostics:
    """Tests for Task 11 score breakdown diagnostics."""

    def test_score_breakdown_stored(self):
        engine = QualityEngine()
        opp = _make_opp(
            title="OWASP Security Scanner",
            url="https://github.com/owasp/scanner",
            description="OWASP vulnerability scanner tool for web application security.",
            source_id="github_search",
            raw_data={"topics": ["owasp", "security"], "language": "Python", "stargazers_count": 150},
        )
        result = engine.evaluate_opportunity(opp)
        assert hasattr(result, "score_breakdown")
        assert "repo_name_score" in result.score_breakdown
        assert "description_score" in result.score_breakdown
        assert "final_confidence" in result.score_breakdown
        assert result.score_breakdown["final_confidence"] == result.confidence_score


class TestQualityEngineDuplicates:
    """Tests for duplicate detection."""

    def test_reject_duplicate_url(self):
        engine = QualityEngine()
        opp1 = _make_opp(title="First Security Opp", url="https://example.com/dupe-test", description="OWASP tool")
        opp2 = _make_opp(title="Second Security Opp", url="https://example.com/dupe-test", description="OWASP tool")
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
