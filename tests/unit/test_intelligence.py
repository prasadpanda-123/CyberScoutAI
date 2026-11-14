"""
Unit tests for Search Intelligence Layer (Phase 2 & Phase B.1.1 Verification).
"""

import unittest

from src.intelligence.taxonomy import KeywordTaxonomy


class TestSearchIntelligence(unittest.TestCase):
    def test_keyword_taxonomy_matching(self):
        """Verify domain knowledge and taxonomies remain fully functional."""
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

    def test_query_builder_physically_removed(self):
        """Verify legacy QueryBuilder module is physically deleted from repository."""
        with self.assertRaises(ModuleNotFoundError):
            import src.intelligence.query_builder  # noqa: F401

    def test_search_planner_physically_removed(self):
        """Verify legacy SearchPlanner module is physically deleted from repository."""
        with self.assertRaises(ModuleNotFoundError):
            import src.intelligence.search_planner  # noqa: F401


if __name__ == "__main__":
    unittest.main()
