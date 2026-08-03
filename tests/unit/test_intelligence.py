"""
Unit tests for Search Intelligence Layer (Phase 2).
"""

import unittest

from src.intelligence.query_builder import QueryBuilder, SearchQuery
from src.intelligence.taxonomy import KeywordTaxonomy


class TestSearchIntelligence(unittest.TestCase):
    def test_keyword_taxonomy_matching(self):
        taxonomy_cfg = {
            "categories": {
                "offensive_security": ["pentest", "ctf", "exploit"],
                "defensive_security": ["soc", "blue team", "siem"],
            }
        }
        taxonomy = KeywordTaxonomy(keywords_config=taxonomy_cfg)
        tags = taxonomy.match_tags("Free CTF competition and pentest workshop")
        self.assertIn("offensive_security", tags)
        self.assertIn("ctf", tags)
        self.assertIn("pentest", tags)

    def test_query_builder(self):
        sources_cfg = {
            "sources": [
                {
                    "id": "cisa_alerts",
                    "collection_method": "rss",
                    "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
                    "enabled": True,
                    "default_category": "security_news",
                },
                {
                    "id": "github_search",
                    "collection_method": "api",
                    "url": "https://api.github.com/search/repositories",
                    "query_params": {"q": "topic:cybersecurity"},
                    "enabled": True,
                },
            ]
        }
        qb = QueryBuilder(sources_config=sources_cfg)
        queries = qb.build_all_queries()
        self.assertEqual(len(queries), 2)

        cisa_q = queries[0]
        self.assertEqual(cisa_q.source_id, "cisa_alerts")
        self.assertEqual(cisa_q.full_url(), "https://www.cisa.gov/cybersecurity-advisories/all.xml")

        gh_q = queries[1]
        self.assertIn("q=topic%3Acybersecurity", gh_q.full_url())


if __name__ == "__main__":
    unittest.main()
