"""
Unit tests for Brevo Email REST API Provider.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from src.notifier.providers.brevo_provider import BrevoEmailProvider
from src.notifier.providers.factory import EmailProviderFactory


class TestBrevoProvider(unittest.TestCase):
    """Tests Brevo REST API provider configuration, health checks, and payload dispatch."""

    def setUp(self):
        self.provider = BrevoEmailProvider(api_key="xkeysib-test-api-key")

    def test_provider_name(self):
        self.assertEqual(self.provider.provider_name, "brevo")

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_health_check(self):
        empty_provider = BrevoEmailProvider(api_key="")
        res = empty_provider.check_health()
        self.assertFalse(res["is_healthy"])
        self.assertEqual(res["stage"], "CONFIG")

    @patch("urllib.request.urlopen")
    def test_check_health_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"email": "test@example.com"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = self.provider.check_health()
        self.assertTrue(res["is_healthy"])
        self.assertEqual(res["provider"], "brevo")
        self.assertEqual(res["https"], "OK")
        self.assertEqual(res["authentication"], "OK")

    @patch("urllib.request.urlopen")
    def test_send_email_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"messageId": "<brevo-12345@brevo>"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = self.provider.send_email(
            html_content="<p>Test</p>",
            plain_content="Test",
            subject="Test Digest",
            attachments=[],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["message_id"], "<brevo-12345@brevo>")

    def test_factory_default(self):
        provider = EmailProviderFactory.get_provider()
        self.assertEqual(provider.provider_name, "brevo")


if __name__ == "__main__":
    unittest.main()
