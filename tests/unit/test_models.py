"""
Unit tests for Core Data Models & Serialization (Phase 1.2).
"""

import unittest

from src.models.enums import CollectionMethod, OpportunityCategory, Status
from src.models.keyword import Keyword
from src.models.opportunity import Opportunity
from src.models.search_models import SearchQuery, SearchResult
from src.models.source import Source
from src.models.stats import ApplicationStatistics, Preferences
from src.utils.validation_utils import is_valid_uuid


class TestModels(unittest.TestCase):
    def test_opportunity_model_serialization(self):
        opp = Opportunity(
            title="PicoCTF 2026",
            url="https://picoctf.org",
            source_id="ctftime",
            category=OpportunityCategory.CTF.value,
        )
        self.assertTrue(is_valid_uuid(opp.id))
        d = opp.to_dict()
        self.assertEqual(d["title"], "PicoCTF 2026")
        restored = Opportunity.from_dict(d)
        self.assertEqual(restored.id, opp.id)

    def test_source_model_serialization(self):
        source = Source(
            id="cisa",
            name="CISA Advisories",
            collection_method=CollectionMethod.RSS.value,
            default_category=OpportunityCategory.SECURITY_NEWS.value,
        )
        d = source.to_dict()
        self.assertEqual(d["id"], "cisa")
        restored = Source.from_dict(d)
        self.assertEqual(restored.name, "CISA Advisories")

    def test_keyword_model_serialization(self):
        kw = Keyword(term="pentest", domain="offensive_security")
        d = kw.to_dict()
        self.assertEqual(d["term"], "pentest")
        restored = Keyword.from_dict(d)
        self.assertEqual(restored.domain, "offensive_security")

    def test_search_models_serialization(self):
        sq = SearchQuery(
            source_id="gh",
            collection_method="api",
            target_url="https://api.github.com/search",
            query_params={"q": "cybersecurity"},
        )
        self.assertIn("q=cybersecurity", sq.full_url())
        sq_dict = sq.to_dict()
        self.assertEqual(sq_dict["source_id"], "gh")

        sr = SearchResult(source_id="gh", raw_items=[{"a": 1}])
        self.assertEqual(sr.item_count, 1)
        sr_dict = sr.to_dict()
        self.assertEqual(sr_dict["item_count"], 1)

    def test_stats_and_preferences_serialization(self):
        stats = ApplicationStatistics(date="2026-08-03", count=42)
        pref = Preferences(key="dark_mode", value="true")

        self.assertEqual(stats.to_dict()["count"], 42)
        self.assertEqual(pref.to_dict()["key"], "dark_mode")


if __name__ == "__main__":
    unittest.main()
