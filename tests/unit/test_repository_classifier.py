"""
Unit tests for RepositoryClassifier (Stage 3 & Repository Analysis).
"""

import unittest
from src.intelligence.repository_classifier import RepositoryClassifier


class TestRepositoryClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = RepositoryClassifier()

    def test_classify_popular_security_repo(self):
        raw_data = {
            "topics": ["security", "owasp", "ctf"],
            "language": "Python",
            "stargazers_count": 150,
            "forks_count": 30,
        }
        score, matched_topics, flags = self.classifier.classify_repository(raw_data)
        self.assertGreaterEqual(score, 70.0)
        self.assertIn("security", matched_topics)
        self.assertIn("POPULAR_REPOSITORY", flags)

    def test_classify_non_security_markup_repo(self):
        raw_data = {
            "topics": ["movies", "streaming"],
            "language": "HTML",
            "stargazers_count": 2,
            "forks_count": 0,
        }
        score, matched_topics, flags = self.classifier.classify_repository(raw_data)
        self.assertIn("NO_SECURITY_TOPICS", flags)
        self.assertIn("PENALIZED_LANGUAGE", flags)
        self.assertEqual(len(matched_topics), 0)


if __name__ == "__main__":
    unittest.main()
