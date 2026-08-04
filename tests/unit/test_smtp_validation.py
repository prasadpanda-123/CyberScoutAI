"""
Unit tests for SMTP Configuration Diagnostics & Validation Framework.
"""

import smtplib
import socket
import unittest
from unittest.mock import MagicMock, patch

from src.core.exceptions import ConfigurationError
from src.core.smtp_validator import SMTPValidator


class TestSMTPValidation(unittest.TestCase):
    """Tests SMTP environment validation, DNS resolution, TCP connectivity, and authentication."""

    def setUp(self):
        self.validator = SMTPValidator()

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_smtp_host_raises_configuration_error(self):
        """Verify missing SMTP_HOST raises ConfigurationError."""
        with patch.object(self.validator, "get_smtp_config") as mock_cfg:
            mock_cfg.return_value = {
                "smtp_host": "",
                "smtp_port_raw": "587",
                "smtp_username": "user@example.com",
                "smtp_password": "pass",
                "email_from": "user@example.com",
                "email_to": "dest@example.com",
                "tls_enabled": True,
                "ssl_enabled": False,
                "env_loaded": False,
            }
            with self.assertRaises(ConfigurationError) as ctx:
                self.validator.validate_configuration()
            self.assertIn("Missing SMTP_HOST", str(ctx.exception))

    def test_invalid_smtp_port_raises_configuration_error(self):
        """Verify non-integer or out-of-range SMTP_PORT raises ConfigurationError."""
        with patch.object(self.validator, "get_smtp_config") as mock_cfg:
            mock_cfg.return_value = {
                "smtp_host": "smtp.gmail.com",
                "smtp_port_raw": "invalid_port",
                "smtp_username": "user@example.com",
                "smtp_password": "pass",
                "email_from": "user@example.com",
                "email_to": "dest@example.com",
                "tls_enabled": True,
                "ssl_enabled": False,
                "env_loaded": True,
            }
            with self.assertRaises(ConfigurationError) as ctx:
                self.validator.validate_configuration()
            self.assertIn("Invalid SMTP_PORT", str(ctx.exception))

    def test_missing_username_raises_configuration_error(self):
        """Verify missing SMTP_USERNAME raises ConfigurationError."""
        with patch.object(self.validator, "get_smtp_config") as mock_cfg:
            mock_cfg.return_value = {
                "smtp_host": "smtp.gmail.com",
                "smtp_port_raw": "587",
                "smtp_username": "",
                "smtp_password": "pass",
                "email_from": "user@example.com",
                "email_to": "dest@example.com",
                "tls_enabled": True,
                "ssl_enabled": False,
                "env_loaded": True,
            }
            with self.assertRaises(ConfigurationError) as ctx:
                self.validator.validate_configuration()
            self.assertIn("Missing SMTP_USERNAME", str(ctx.exception))

    def test_missing_password_raises_configuration_error(self):
        """Verify missing SMTP_PASSWORD raises ConfigurationError."""
        with patch.object(self.validator, "get_smtp_config") as mock_cfg:
            mock_cfg.return_value = {
                "smtp_host": "smtp.gmail.com",
                "smtp_port_raw": "587",
                "smtp_username": "user@example.com",
                "smtp_password": "",
                "email_from": "user@example.com",
                "email_to": "dest@example.com",
                "tls_enabled": True,
                "ssl_enabled": False,
                "env_loaded": True,
            }
            with self.assertRaises(ConfigurationError) as ctx:
                self.validator.validate_configuration()
            self.assertIn("Missing SMTP_PASSWORD", str(ctx.exception))

    @patch("socket.getaddrinfo")
    def test_invalid_hostname_dns_failure(self, mock_getaddrinfo):
        """Verify DNS resolution failure returns clean message instead of traceback."""
        mock_getaddrinfo.side_effect = socket.gaierror(11001, "getaddrinfo failed")
        success, msg = self.validator.verify_dns("invalid-nonexistent-domain-12345.com")
        self.assertFalse(success)
        self.assertIn("Invalid SMTP hostname", msg)

    @patch("smtplib.SMTP")
    def test_authentication_failure(self, mock_smtp_cls):
        """Verify SMTP authentication failure returns clean message."""
        mock_instance = MagicMock()
        mock_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Bad credentials")
        mock_smtp_cls.return_value = mock_instance

        success, msg = self.validator.verify_authentication(
            host="smtp.gmail.com",
            port=587,
            username="user@gmail.com",
            password="wrong_password",
        )
        self.assertFalse(success)
        self.assertIn("Authentication failed", msg)

    @patch("smtplib.SMTP")
    def test_successful_gmail_login_mocked(self, mock_smtp_cls):
        """Verify successful SMTP login returns Authenticated."""
        mock_instance = MagicMock()
        mock_smtp_cls.return_value = mock_instance

        success, msg = self.validator.verify_authentication(
            host="smtp.gmail.com",
            port=587,
            username="user@gmail.com",
            password="app_password",
        )
        self.assertTrue(success)
        self.assertEqual(msg, "Authenticated")


if __name__ == "__main__":
    unittest.main()
