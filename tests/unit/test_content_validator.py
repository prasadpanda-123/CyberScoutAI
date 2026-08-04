"""
Unit Tests for ContentValidator (Phase 11.5).
"""

import pytest
from src.intelligence.content_validator import ContentValidator


class TestContentValidator:
    """Tests for Stage 1 basic content validation."""

    def test_valid_opportunity(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="OWASP Security Internship 2026",
            url="https://example.com/owasp-internship",
            description="A comprehensive internship program covering OWASP Top 10 vulnerabilities and web security testing.",
        )
        assert is_valid
        assert reason is None

    def test_reject_empty_title(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="",
            url="https://example.com/test",
            description="Some description here.",
        )
        assert not is_valid
        assert reason == "INVALID_CONTENT"

    def test_reject_none_title(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title=None,
            url="https://example.com/test",
        )
        assert not is_valid

    def test_reject_short_title(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="Hi",
            url="https://example.com/test",
            description="Some valid description text here for testing.",
        )
        assert not is_valid

    def test_reject_empty_url(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="Valid Title Here",
            url="",
        )
        assert not is_valid

    def test_reject_invalid_url(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="Valid Title Here",
            url="not-a-valid-url",
        )
        assert not is_valid

    def test_accept_short_description_for_cve(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="CVE-2026-12345 Advisory",
            url="https://cisa.gov/advisory/12345",
            description="Critical RCE",
        )
        assert is_valid

    def test_accept_short_description_for_security(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="Security Patch Released",
            url="https://example.com/patch",
            description="Patch fix",
        )
        assert is_valid

    def test_reject_short_description_for_generic(self):
        validator = ContentValidator()
        is_valid, reason, msg = validator.validate(
            title="Some Generic Tool",
            url="https://example.com/tool",
            description="Short",
        )
        assert not is_valid
