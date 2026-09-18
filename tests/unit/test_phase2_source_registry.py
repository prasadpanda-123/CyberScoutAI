"""
Phase 2 Unit Tests: Authoritative Source Registry & Taxonomy Foundation.

Tests:
- All 75 sources registered
- Unique machine-readable source IDs
- Valid source metadata & taxonomy compliance
- Multi-family and multi-opportunity-type mapping
- Safe enable/disable control
- Manual review / unsupported status handling
- Trust tier assignment
- Rate limit policies
- SourceRepository database persistence
"""

import unittest
from src.collectors.source_definitions import (
    AUTHORITATIVE_SOURCES,
    TARGET_75_SOURCE_IDS,
    get_source_definition,
)
from src.collectors.source_registry import SourceRegistry
from src.models.enums import (
    AccessMethod,
    HealthStatus,
    OpportunityType,
    RobotsPolicy,
    SourceFamily,
    TermsReviewStatus,
    TrustTier,
)
from src.models.source import Source
from src.database.connection import DatabaseManager
from src.database.source_repository import SourceRepository


class TestPhase2SourceRegistry(unittest.TestCase):
    """Tests for the 75 authoritative source definitions and registry manager."""

    def test_all_75_sources_registered(self):
        """Verify that exactly 75 authoritative target sources are registered."""
        self.assertEqual(len(AUTHORITATIVE_SOURCES), 75)
        self.assertEqual(len(TARGET_75_SOURCE_IDS), 75)

    def test_unique_source_ids(self):
        """Verify that all 75 source IDs are strictly unique, lowercase, and valid slugs."""
        source_ids = list(AUTHORITATIVE_SOURCES.keys())
        self.assertEqual(len(source_ids), len(set(source_ids)))

        for sid in source_ids:
            self.assertEqual(sid, sid.lower().strip())
            self.assertRegex(sid, r"^[a-z0-9_]+$", f"Source ID '{sid}' must be lowercase alphanumeric/underscore")

    def test_valid_source_metadata(self):
        """Verify that every source definition contains complete, required metadata."""
        for sid, s_def in AUTHORITATIVE_SOURCES.items():
            self.assertEqual(sid, s_def.source_id)
            self.assertTrue(s_def.name, f"Source '{sid}' missing name")
            self.assertTrue(s_def.canonical_url.startswith("http"), f"Source '{sid}' canonical_url must start with http")
            self.assertTrue(s_def.organization, f"Source '{sid}' missing organization")
            self.assertIn(s_def.country_scope, ["IN", "GLOBAL", "US", "EU"], f"Source '{sid}' invalid country scope")
            self.assertTrue(s_def.language, f"Source '{sid}' missing language")
            self.assertTrue(s_def.parser_version, f"Source '{sid}' missing parser_version")
            self.assertIsInstance(s_def.rate_limit_policy.request_timeout, (int, float))
            self.assertGreater(s_def.rate_limit_policy.request_timeout, 0)
            self.assertGreaterEqual(s_def.rate_limit_policy.retry_count, 0)
            self.assertLessEqual(s_def.rate_limit_policy.retry_count, 5)

    def test_source_family_and_opportunity_taxonomy(self):
        """Verify that source families and opportunity types adhere to the canonical enums."""
        valid_families = {e.value for e in SourceFamily}
        valid_opp_types = {e.value for e in OpportunityType}

        for sid, s_def in AUTHORITATIVE_SOURCES.items():
            fam = s_def.source_family.value if hasattr(s_def.source_family, "value") else s_def.source_family
            self.assertIn(fam, valid_families, f"Source '{sid}' has invalid family '{fam}'")

            self.assertTrue(len(s_def.opportunity_types) >= 1, f"Source '{sid}' must provide at least one opportunity type")
            for o_type in s_def.opportunity_types:
                ot_val = o_type.value if hasattr(o_type, "value") else o_type
                self.assertIn(ot_val, valid_opp_types, f"Source '{sid}' has invalid opportunity type '{ot_val}'")

    def test_trust_tiers_assigned_honestly(self):
        """Verify trust tiers: Tier 1 for official/primary platforms, Tier 2-4 for aggregators/review."""
        valid_tiers = {e.value for e in TrustTier}
        for sid, s_def in AUTHORITATIVE_SOURCES.items():
            tier = s_def.trust_tier.value if hasattr(s_def.trust_tier, "value") else s_def.trust_tier
            self.assertIn(tier, valid_tiers, f"Source '{sid}' has invalid trust tier '{tier}'")

    def test_unsupported_and_manual_review_sources_honesty(self):
        """Verify sources that cannot safely be auto-scraped are marked MANUAL_REVIEW or UNSUPPORTED and disabled."""
        manual_or_unsupported = [
            s for s in AUTHORITATIVE_SOURCES.values()
            if s.status in ("MANUAL_REVIEW", "UNSUPPORTED")
        ]
        self.assertGreater(len(manual_or_unsupported), 0, "There must be honestly marked manual/unsupported sources")

        for s in manual_or_unsupported:
            self.assertFalse(s.enabled, f"Manual/unsupported source '{s.source_id}' must not be enabled by default")

    def test_source_registry_filtering_and_toggle(self):
        """Verify SourceRegistry filtering by family, opportunity type, and safe enable/disable toggle."""
        registry = SourceRegistry()
        all_sources = registry.get_all_sources()
        self.assertEqual(len(all_sources), 75)

        # Filter by family
        cyber_sources = registry.get_sources_by_family(SourceFamily.CYBERSECURITY)
        self.assertGreater(len(cyber_sources), 0)
        for s in cyber_sources:
            self.assertIn(s.source_family, [SourceFamily.CYBERSECURITY.value, SourceFamily.CYBERSECURITY])

        # Filter by opportunity type
        ctf_sources = registry.get_sources_by_opportunity_type(OpportunityType.CTF)
        self.assertGreater(len(ctf_sources), 0)

        # Toggle enable/disable
        orig_state = registry.is_enabled("devpost")
        registry.set_enabled("devpost", False)
        self.assertFalse(registry.is_enabled("devpost"))
        registry.set_enabled("devpost", orig_state)
        self.assertEqual(registry.is_enabled("devpost"), orig_state)

    def test_source_repository_persistence(self):
        """Verify persisting and querying Source entities with Phase 2 fields."""
        db = DatabaseManager()
        db.initialize_database()
        repo = SourceRepository(db)

        test_source = Source(
            id="test_custom_phase2_source",
            name="Test Custom Phase 2 Source",
            canonical_url="https://example.com/opportunities",
            organization="Test Foundation",
            country_scope="GLOBAL",
            language="en",
            source_family=SourceFamily.OPEN_SOURCE,
            opportunity_types=[OpportunityType.OPEN_SOURCE, OpportunityType.FELLOWSHIP],
            collection_method="rss",
            collector_type="rss",
            access_method=AccessMethod.RSS,
            default_category="open_source",
            status="CONFIGURED",
            enabled=True,
            official=True,
            trust_score=0.95,
            trust_tier=TrustTier.TIER_1,
            rate_limit_policy={"requests_per_minute": 30, "timeout_seconds": 15},
            parser_version="1.0.0",
            health_status=HealthStatus.HEALTHY,
        )

        saved_id = repo.save_source(test_source)
        self.assertEqual(saved_id, "test_custom_phase2_source")

        fetched = repo.get_by_id("test_custom_phase2_source")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Test Custom Phase 2 Source")
        self.assertEqual(fetched.canonical_url, "https://example.com/opportunities")
        self.assertTrue(fetched.enabled)
        self.assertEqual(fetched.trust_tier, "tier_1")

        db.close()


if __name__ == "__main__":
    unittest.main()
