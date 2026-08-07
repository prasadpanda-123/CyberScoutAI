"""
Unit tests for Core Collectors (Phase 3.2).
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.collectors.ctftime_collector import CtftimeCollector
from src.collectors.github_collector import GithubSearchCollector
from src.collectors.manager import CollectorManager
from src.collectors.rss_collector import GenericRSSCollector
from src.collectors.youtube_collector import YouTubeRSSCollector
from src.intelligence.planner_models import SearchTask


def _make_mock_response(text_content: str, status_code: int = 200):
    mock_res = MagicMock()
    mock_res.status_code = status_code
    mock_res.text = text_content
    mock_res.raise_for_status.return_value = None
    return mock_res


class TestCoreCollectors(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cache.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("requests.Session.get")
    def test_generic_rss_collector(self, mock_get):
        rss_content = """<rss><channel><item><title>CISA Advisory 1</title><link>https://cisa.gov/adv1</link><description>Alert details</description></item></channel></rss>"""
        mock_get.return_value = _make_mock_response(rss_content)

        collector = GenericRSSCollector()
        task = SearchTask(
            source_id="cisa_alerts",
            query_text="advisory",
            target_url="https://cisa.gov/rss.xml",
            category="security_news",
            collection_method="rss",
        )
        result = collector.collect(task)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0]["title"], "CISA Advisory 1")
        self.assertEqual(result.items[0]["url"], "https://cisa.gov/adv1")

    @patch("requests.Session.get")
    def test_github_search_collector(self, mock_get):
        json_content = """{
            "items": [
                {
                    "full_name": "owner/cyber-tool",
                    "html_url": "https://github.com/owner/cyber-tool",
                    "stargazers_count": 150,
                    "description": "A security tool",
                    "topics": ["cybersecurity", "tool"]
                }
            ]
        }"""
        mock_get.return_value = _make_mock_response(json_content)

        collector = GithubSearchCollector()
        task = SearchTask(
            source_id="github_search",
            query_text="cyber tool",
            target_url="https://api.github.com/search/repositories?q=cyber+tool",
            category="github_repository",
            collection_method="api",
        )
        result = collector.collect(task)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)
        self.assertIn("cyber-tool", result.items[0]["title"])
        self.assertEqual(result.items[0]["url"], "https://github.com/owner/cyber-tool")

    @patch("requests.Session.get")
    def test_youtube_rss_collector(self, mock_get):
        atom_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
            <entry>
                <title>IppSec HackTheBox Walkthrough</title>
                <link href="https://www.youtube.com/watch?v=123"/>
                <author><name>IppSec</name></author>
                <published>2026-08-01T12:00:00Z</published>
            </entry>
        </feed>"""
        mock_get.return_value = _make_mock_response(atom_content)

        collector = YouTubeRSSCollector()
        task = SearchTask(
            source_id="ippsec",
            query_text="walkthrough",
            target_url="https://www.youtube.com/feeds/videos.xml?channel_id=UCa6TeYZ265fvuCTv035PDfA",
            category="course",
            collection_method="rss",
        )
        result = collector.collect(task)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)
        self.assertIn("IppSec", result.items[0]["title"])

    @patch("requests.Session.get")
    def test_ctftime_collector(self, mock_get):
        ctf_json = """[
            {
                "title": "PicoCTF 2026",
                "url": "https://picoctf.org",
                "ctftime_url": "https://ctftime.org/event/123",
                "weight": 25.0,
                "format": "Jeopardy",
                "start": "2026-09-01T00:00:00Z",
                "finish": "2026-09-10T00:00:00Z"
            }
        ]"""
        mock_get.return_value = _make_mock_response(ctf_json)

        collector = CtftimeCollector()
        task = SearchTask(
            source_id="ctftime",
            query_text="picoctf",
            target_url="https://ctftime.org/api/v1/events/",
            category="ctf",
            collection_method="api",
        )
        result = collector.collect(task)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0]["title"], "CTF: PicoCTF 2026")

    @patch("requests.Session.get")
    def test_collector_manager_with_core_collectors(self, mock_get):
        rss_content = """<rss><channel><item><title>Security News</title><link>https://example.com/news</link></item></channel></rss>"""
        mock_get.return_value = _make_mock_response(rss_content)

        manager = CollectorManager()
        task = SearchTask(
            source_id="cisa_alerts",
            query_text="news",
            target_url="https://example.com/rss",
            category="security_news",
            collection_method="rss",
            metadata={"preferred_collector": "GenericRSSCollector"},
        )
        result = manager.execute_task(task)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)


if __name__ == "__main__":
    unittest.main()
