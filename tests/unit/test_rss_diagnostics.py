"""
Unit tests for RSS/XML Parser Diagnostics & Recovery Framework.
"""

from pathlib import Path
import unittest

from src.collectors.parser_utils import parse_rss_xml_content
from src.core.constants import PROJECT_ROOT
from src.core.rss_diagnostics import RSSDiagnosticsManager, RSS_ERRORS_DIR


class TestRSSDiagnosticsFramework(unittest.TestCase):
    """Tests RSS XML parsing diagnostics, error logging, HTML/JSON detection, and recovery."""

    def setUp(self):
        self.diag_mgr = RSSDiagnosticsManager()

    def test_valid_rss_xml_parsing(self):
        """Verify valid RSS XML content parses cleanly."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Security News</title>
                <item>
                    <title>New Zero-Day Vulnerability Discovered</title>
                    <link>https://example.com/sec-news-1</link>
                    <description>Critical vulnerability details.</description>
                    <pubDate>Mon, 03 Aug 2026 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        items = parse_rss_xml_content(
            content=xml_content,
            source_id="test_feed",
            url="https://example.com/rss",
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "New Zero-Day Vulnerability Discovered")

    def test_detect_html_response_recommends_html_scraper(self):
        """Verify HTML response (e.g. 404 page or Cloudflare) recommends HtmlScraperCollector."""
        html_content = """<!DOCTYPE html>
        <html>
        <head><title>404 Not Found</title></head>
        <body><h1>Page Not Found</h1></body>
        </html>"""

        items = parse_rss_xml_content(
            content=html_content,
            source_id="html_test_feed",
            url="https://example.com/404",
            content_type="text/html",
        )
        self.assertEqual(len(items), 0)

        records = self.diag_mgr.get_all_records()
        html_records = [r for r in records if r.source_id == "html_test_feed"]
        self.assertGreater(len(html_records), 0)
        self.assertIn("HtmlScraperCollector", html_records[-1].recommendation)

    def test_detect_cloudflare_page(self):
        """Verify Cloudflare verification page detects HTML and recommends HtmlScraperCollector."""
        cf_content = """<html>
        <head><title>Just a moment...</title></head>
        <body><div id="cf-browser-verification">Verifying your browser...</div></body>
        </html>"""

        items = parse_rss_xml_content(
            content=cf_content,
            source_id="cloudflare_test_feed",
            url="https://example.com/cf",
        )
        self.assertEqual(len(items), 0)

        records = self.diag_mgr.get_all_records()
        cf_records = [r for r in records if r.source_id == "cloudflare_test_feed"]
        self.assertGreater(len(cf_records), 0)
        self.assertIn("HtmlScraperCollector", cf_records[-1].recommendation)

    def test_detect_json_response_recommends_json_collector(self):
        """Verify JSON response detects JSON and recommends JSON collector."""
        json_content = '{"status": "ok", "items": [{"id": 1, "name": "Event"}]}'

        items = parse_rss_xml_content(
            content=json_content,
            source_id="json_test_feed",
            url="https://example.com/api",
            content_type="application/json",
        )
        self.assertEqual(len(items), 0)

        records = self.diag_mgr.get_all_records()
        json_records = [r for r in records if r.source_id == "json_test_feed"]
        self.assertGreater(len(json_records), 0)
        self.assertIn("JSON", json_records[-1].recommendation)

    def test_malformed_xml_recovery_using_sanitization(self):
        """Verify unescaped ampersands in XML are recovered via sanitization."""
        malformed_xml = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Security & Tech News Update</title>
                    <link>https://example.com/item1</link>
                    <description>Research & Development & Testing</description>
                </item>
            </channel>
        </rss>"""

        items = parse_rss_xml_content(
            content=malformed_xml,
            source_id="malformed_feed",
            url="https://example.com/malformed",
        )
        self.assertEqual(len(items), 1)
        self.assertIn("Security", items[0]["title"])

    def test_error_dump_saved_to_disk(self):
        """Verify malformed XML dump file is saved under logs/rss_errors/."""
        bad_xml = "<rss><channel><item><title>Broken XML"
        parse_rss_xml_content(
            content=bad_xml,
            source_id="dump_test_feed",
            url="https://example.com/dump",
        )
        records = self.diag_mgr.get_all_records()
        dump_records = [r for r in records if r.source_id == "dump_test_feed"]
        self.assertGreater(len(dump_records), 0)
        saved_file = dump_records[-1].file_saved
        self.assertIsNotNone(saved_file)
        self.assertTrue(Path(saved_file).exists())


if __name__ == "__main__":
    unittest.main()
