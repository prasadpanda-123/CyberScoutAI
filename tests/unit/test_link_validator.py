import socket
import unittest
from unittest.mock import MagicMock, patch
from src.intelligence.production.link_validator import LinkValidator


class TestLinkValidator(unittest.TestCase):
    def setUp(self):
        self.validator = LinkValidator(timeout=2.0)

    @patch("socket.gethostbyname", return_value="93.184.216.34")
    @patch("urllib.request.urlopen")
    def test_valid_domain_link(self, mock_urlopen, mock_dns):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response

        is_valid, code, msg = self.validator.validate_url("https://example.com/test-opportunity")
        self.assertTrue(is_valid)
        self.assertEqual(code, 200)

    def test_invalid_scheme_link(self):
        is_valid, code, msg = self.validator.validate_url("ftp://example.com/file")
        self.assertFalse(is_valid)
        self.assertEqual(code, 400)

    @patch("socket.gethostbyname", side_effect=socket.gaierror("[Errno 11001] getaddrinfo failed"))
    def test_dead_dns_link(self, mock_dns):
        is_valid, code, msg = self.validator.validate_url("https://thisdomainshouldneverexist999111.org/path")
        self.assertFalse(is_valid)
        self.assertEqual(code, 502)


if __name__ == "__main__":
    unittest.main()
