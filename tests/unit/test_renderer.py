"""
Unit tests for Notifier HTML & Plain Text Renderer (Phase 7).
"""

import unittest

from src.models.opportunity import Opportunity
from src.notifier.base import ReportDigest
from src.notifier.html_renderer import HTMLRenderer


class TestHTMLRenderer(unittest.TestCase):
    def test_render_report(self):
        digest = ReportDigest(
            date="2026-08-03",
            total_opportunities=1,
            categories={
                "scholarship": [
                    Opportunity(
                        title="SANS FastTrack",
                        url="https://example.com",
                        source_id="sans",
                        category="scholarship",
                        score=90,
                    )
                ]
            },
            stats={
                "total_opportunities": 1,
                "high_priority_count": 1,
                "average_score": 90.0,
            },
        )

        renderer = HTMLRenderer()
        html, text = renderer.render_report(digest)

        self.assertIn("SANS FastTrack", html)
        self.assertIn("SANS FastTrack", text)
        self.assertIn("Score: 90", html)
        self.assertIn("Average Score: 90.0", text)


if __name__ == "__main__":
    unittest.main()
