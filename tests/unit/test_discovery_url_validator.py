"""
Unit Tests for Discovery URL Security and SSRF Validator.

Verifies strict rejection of:
- Localhost, 127.0.0.1, 0.0.0.0, ::1
- RFC 1918 Private IP subnets
- Cloud metadata endpoints (169.254.169.254)
- Dangerous pseudo-protocols (file://, javascript:, data:, blob:)
- Malformed URLs and credentials in URLs
- Dangerous executable file extensions
- DNS rebinding resolution to prohibited addresses
"""

import socket
from unittest.mock import patch
import pytest

from src.discovery.url_validator import URLValidator, URLValidationResult


class TestDiscoveryURLValidator:

    def setup_method(self):
        self.validator = URLValidator(resolve_dns=False)

    def test_valid_public_https_url(self):
        """Valid public HTTPS web URLs must pass validation."""
        result = self.validator.validate("https://ctftime.org/event/2026")
        assert result.is_valid is True
        assert result.canonical_url.startswith("https://ctftime.org/event/2026")
        assert len(result.url_hash) == 64
        assert result.domain == "ctftime.org"
        assert result.rejection_reason is None

    def test_valid_public_http_url(self):
        """Valid public HTTP URLs must pass validation."""
        result = self.validator.validate("http://example.com/cybersecurity-internship")
        assert result.is_valid is True
        assert result.domain == "example.com"
        assert result.rejection_reason is None

    def test_reject_empty_or_none_url(self):
        """Empty or None URLs must be rejected safely."""
        assert self.validator.validate("").is_valid is False
        assert self.validator.validate(None).is_valid is False
        assert self.validator.validate("   ").is_valid is False

    def test_reject_localhost_string(self):
        """Literal localhost hostname must be rejected."""
        result = self.validator.validate("http://localhost:8000/api")
        assert result.is_valid is False
        assert "localhost" in result.rejection_reason.lower()

    def test_reject_loopback_ipv4(self):
        """127.0.0.1 and 127.0.0.0/8 loopback IPs must be rejected."""
        assert self.validator.validate("http://127.0.0.1/admin").is_valid is False
        assert self.validator.validate("http://127.0.1.5:5000").is_valid is False

    def test_reject_loopback_ipv6(self):
        """IPv6 loopback [::1] must be rejected."""
        result = self.validator.validate("http://[::1]/secret")
        assert result.is_valid is False
        assert "prohibited" in result.rejection_reason.lower() or "loopback" in result.rejection_reason.lower()

    def test_reject_cloud_metadata_ip(self):
        """Cloud metadata endpoint 169.254.169.254 must be strictly rejected."""
        result = self.validator.validate("http://169.254.169.254/latest/meta-data/")
        assert result.is_valid is False
        assert "prohibited" in result.rejection_reason.lower()

    def test_reject_rfc1918_private_ips(self):
        """RFC 1918 subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) must be rejected."""
        assert self.validator.validate("http://10.0.0.1/").is_valid is False
        assert self.validator.validate("http://172.16.0.5/").is_valid is False
        assert self.validator.validate("http://192.168.1.1/dashboard").is_valid is False

    def test_reject_carrier_grade_nat_and_zero(self):
        """CGNAT (100.64.0.0/10) and 0.0.0.0 must be rejected."""
        assert self.validator.validate("http://0.0.0.0:80/").is_valid is False
        assert self.validator.validate("http://100.64.0.1/").is_valid is False

    def test_reject_forbidden_pseudo_protocols(self):
        """file:, javascript:, data:, blob:, gopher: must be rejected."""
        assert self.validator.validate("file:///etc/passwd").is_valid is False
        assert self.validator.validate("javascript:alert(1)").is_valid is False
        assert self.validator.validate("data:text/html,<h1>Test</h1>").is_valid is False
        assert self.validator.validate("blob:https://example.com/uuid").is_valid is False
        assert self.validator.validate("gopher://127.0.0.1:70/").is_valid is False
        assert self.validator.validate("ftp://example.com/file").is_valid is False

    def test_reject_control_characters_and_crlf(self):
        """CRLF injection and control chars must be rejected."""
        assert self.validator.validate("http://example.com/path\r\nHeader: Value").is_valid is False
        assert self.validator.validate("http://example.com/path\x00malicious").is_valid is False

    def test_reject_embedded_user_credentials(self):
        """URLs containing username:password must be rejected."""
        result = self.validator.validate("http://admin:secret@example.com/path")
        assert result.is_valid is False
        assert "credentials" in result.rejection_reason.lower()

    def test_reject_wildcard_localhost_domains(self):
        """Wildcard localhost domains (e.g. localtest.me, nip.io) must be rejected."""
        assert self.validator.validate("http://something.localtest.me/").is_valid is False
        assert self.validator.validate("http://127.0.0.1.nip.io/").is_valid is False

    def test_reject_prohibited_executable_extensions(self):
        """Direct links to executables/archives (.exe, .zip, .sh, .bat) must be rejected."""
        assert self.validator.validate("https://example.com/payload.exe").is_valid is False
        assert self.validator.validate("https://example.com/archive.zip").is_valid is False
        assert self.validator.validate("https://example.com/install.sh").is_valid is False

    def test_reject_numeric_decimal_ip_encodings(self):
        """Integer representation of 127.0.0.1 (2130706433) must be parsed and rejected."""
        result = self.validator.validate("http://2130706433/admin")
        assert result.is_valid is False
        assert "prohibited" in result.rejection_reason.lower()

    def test_dns_rebinding_resolution_protection(self):
        """When resolve_dns=True, hostnames resolving to private IPs must be rejected."""
        dns_validator = URLValidator(resolve_dns=True, dns_timeout=1.0)

        # Mock socket.getaddrinfo to simulate evil-domain.com resolving to 127.0.0.1
        mock_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with patch("socket.getaddrinfo", return_value=mock_addrinfo):
            result = dns_validator.validate("https://evil-rebinding-domain.com/login")
            assert result.is_valid is False
            assert "dns resolved to prohibited ip" in result.rejection_reason.lower()

    def test_dns_rebinding_metadata_resolution_protection(self):
        """When resolve_dns=True, hostnames resolving to 169.254.169.254 must be rejected."""
        dns_validator = URLValidator(resolve_dns=True, dns_timeout=1.0)

        mock_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]
        with patch("socket.getaddrinfo", return_value=mock_addrinfo):
            result = dns_validator.validate("https://attacker-cname-metadata.com/latest")
            assert result.is_valid is False
            assert "169.254.169.254" in result.rejection_reason

