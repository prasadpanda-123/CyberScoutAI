"""
Unit tests for TopicAnalyzer (Stage 2: Repository Topic Analysis).
"""

import unittest
from src.intelligence.topic_analyzer import TopicAnalyzer


class TestTopicAnalysis(unittest.TestCase):
    def setUp(self):
        self.analyzer = TopicAnalyzer()

    def test_approved_security_topics(self):
        topics = ["security", "ctf", "malware-analysis", "pentesting"]
        score, matched, has_sec = self.analyzer.analyze_topics(topics)
        self.assertTrue(has_sec)
        self.assertGreater(score, 50.0)
        self.assertIn("security", matched)
        self.assertIn("ctf", matched)

    def test_unapproved_topics(self):
        topics = ["iptv", "streaming", "movies"]
        score, matched, has_sec = self.analyzer.analyze_topics(topics)
        self.assertFalse(has_sec)
        self.assertEqual(score, 0.0)
        self.assertEqual(len(matched), 0)

    def test_empty_topics(self):
        score, matched, has_sec = self.analyzer.analyze_topics([])
        self.assertTrue(has_sec)
        self.assertEqual(score, 0.0)
        self.assertEqual(len(matched), 0)


if __name__ == "__main__":
    unittest.main()
