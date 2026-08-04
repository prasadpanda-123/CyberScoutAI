"""
Unit Tests for SpamDetector & Blacklist Engine (Phase 11.5).
"""

import pytest
from src.intelligence.spam_detector import SpamDetector


class TestBlacklistEngine:
    """Tests for Stage 5 instant discard blacklist."""

    def test_detect_iptv(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("Free IPTV channels list 2026")
        assert is_bl
        assert "iptv" in term.lower()

    def test_detect_extm3u(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("#EXTM3U\n#EXTINF:-1,Channel")
        assert is_bl

    def test_detect_torrent(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("Download free torrent files")
        assert is_bl

    def test_detect_movie(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("Watch free movies online")
        assert is_bl

    def test_detect_anime(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("Best anime streaming sites")
        assert is_bl

    def test_pass_legitimate_security(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("OWASP Top 10 Security Vulnerabilities")
        assert not is_bl

    def test_pass_cve_advisory(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("CVE-2026-12345 Remote Code Execution in Apache")
        assert not is_bl

    def test_pass_empty_text(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist("")
        assert not is_bl

    def test_pass_none_text(self):
        detector = SpamDetector()
        is_bl, term = detector.check_blacklist(None)
        assert not is_bl


class TestReadmeSpamAnalysis:
    """Tests for Stage 6 README structure analysis."""

    def test_detect_media_extensions(self):
        detector = SpamDetector()
        readme = "\n".join([
            "channel1.m3u8",
            "stream.ts",
            "video.mp4",
            "audio.mp3",
            "movie.mkv",
            "song.flac",
        ])
        is_spam, score, reason = detector.analyze_readme_structure(readme)
        assert is_spam
        assert "PLAYLIST" in reason

    def test_detect_excessive_urls(self):
        detector = SpamDetector()
        urls = "\n".join([f"https://example.com/link-{i}" for i in range(250)])
        is_spam, score, reason = detector.analyze_readme_structure(urls)
        assert is_spam
        assert "URLS" in reason

    def test_detect_repeated_lines(self):
        detector = SpamDetector()
        readme = "\n".join(["Same line content"] * 50)
        is_spam, score, reason = detector.analyze_readme_structure(readme)
        assert is_spam
        assert "REPEATED" in reason

    def test_pass_legitimate_readme(self):
        detector = SpamDetector()
        readme = """
# Security Scanner
A Python-based vulnerability scanner that checks for OWASP Top 10 issues.
## Installation
pip install security-scanner
## Usage
Run `scanner --target example.com` to start scanning.
"""
        is_spam, score, reason = detector.analyze_readme_structure(readme)
        assert not is_spam

    def test_pass_empty_readme(self):
        detector = SpamDetector()
        is_spam, score, reason = detector.analyze_readme_structure("")
        assert not is_spam
