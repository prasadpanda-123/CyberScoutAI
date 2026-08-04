"""
Unit Tests for KeywordClassifier (Phase 11.5).
"""

import pytest
from src.intelligence.keyword_classifier import KeywordClassifier


class TestKeywordClassifier:
    """Tests for cybersecurity keyword matching."""

    def test_match_owasp(self):
        classifier = KeywordClassifier()
        score, matched = classifier.classify_keywords(
            title="OWASP Top 10 Vulnerabilities",
            description="Understanding OWASP security risks.",
        )
        assert score > 0
        assert any("owasp" in k.lower() for k in matched)

    def test_match_cve(self):
        classifier = KeywordClassifier()
        score, matched = classifier.classify_keywords(
            title="CVE-2026-12345 Analysis",
            description="Critical CVE affecting web servers.",
        )
        assert score > 0
        assert any("cve" in k.lower() for k in matched)

    def test_match_multiple_keywords(self):
        classifier = KeywordClassifier()
        score, matched = classifier.classify_keywords(
            title="SOC Analyst CTF Walkthrough",
            description="Using Wireshark, Nmap, and Metasploit in a CTF competition.",
        )
        assert score >= 50.0
        assert len(matched) >= 2

    def test_no_match_generic(self):
        classifier = KeywordClassifier()
        score, matched = classifier.classify_keywords(
            title="JavaScript Framework Comparison",
            description="React vs Vue vs Angular performance benchmarks.",
        )
        assert score == 0.0
        assert matched == []

    def test_match_in_readme(self):
        classifier = KeywordClassifier()
        score, matched = classifier.classify_keywords(
            title="Security Tools Collection",
            readme="This repository contains tools for SQL Injection testing and XSS detection.",
        )
        assert score > 0

    def test_match_in_topics(self):
        classifier = KeywordClassifier()
        score, matched = classifier.classify_keywords(
            title="Network Scanner",
            topics=["nmap", "wireshark", "forensics"],
        )
        assert score > 0

    def test_score_capped_at_100(self):
        classifier = KeywordClassifier()
        score, matched = classifier.classify_keywords(
            title="OWASP CVE Exploit Vulnerability XSS CSRF Malware Forensics CTF Nmap",
            description="SOC SIEM IDS Wireshark Metasploit YARA Sigma Burp Suite",
        )
        assert score <= 100.0
