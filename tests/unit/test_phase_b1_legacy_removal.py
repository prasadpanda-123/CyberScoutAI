"""
Comprehensive Verification Test Suite for CyberScout AI Phase B.1 & B.1.1.

Verifies complete physical removal of legacy word-list and static URL discovery:
1. search_planner.py is physically deleted (import raises ModuleNotFoundError).
2. query_builder.py is physically deleted (import raises ModuleNotFoundError).
3. template_engine.py is physically deleted (import raises ModuleNotFoundError).
4. query_validator.py is physically deleted (import raises ModuleNotFoundError).
5. html_collector.py is physically deleted (import raises ModuleNotFoundError).
6. No obsolete discovery modules remain in active import paths (src.intelligence.__all__, src.collectors).
7. config/search_templates.yaml is physically deleted from repository.
8. Tavily discovery engine is the sole active discovery provider in pipeline.py.
9. Tavily discovery failure NEVER triggers fallback to old discovery system.
10. PipelineRunner and run_pipeline_once reject legacy search_planner with RuntimeError.
11. Staged candidates are stored with correct source and status attributes in DiscoveredCandidates.
12. Staged candidates are isolated from production Opportunities table until Phase C extraction.
13. Useful taxonomies, categories, and registries are fully preserved.
"""

from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock

import src.collectors.registry
import src.intelligence
from src.automation.pipeline import PipelineRunner, run_pipeline_once
from src.database.connection import DatabaseManager
from src.discovery.discovery_models import (
    CandidateProcessingStatus,
    DiscoveredCandidate,
    DiscoveryRunSummary,
    GeographicRegion,
    OpportunityCategory,
    PricingVerificationStatus,
)
from src.discovery.discovery_service import GlobalDiscoveryService
from src.discovery.platform_registry import PlatformRegistry
from src.discovery.region_registry import RegionRegistry
from src.intelligence.keyword_engine import KeywordEngine
from src.intelligence.source_registry import SourceRegistry
from src.intelligence.taxonomy import KeywordTaxonomy


class TestPhaseB1LegacyDiscoveryPhysicalRemoval(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()

    def test_01_search_planner_physically_deleted(self):
        """Verify search_planner.py is deleted and cannot be imported."""
        path = Path("CyberScoutAI/src/intelligence/search_planner.py")
        if not path.exists():
            path = Path("src/intelligence/search_planner.py")
        self.assertFalse(path.exists(), "src/intelligence/search_planner.py must be physically deleted")

        with self.assertRaises(ModuleNotFoundError):
            import src.intelligence.search_planner  # noqa: F401

    def test_02_query_builder_physically_deleted(self):
        """Verify query_builder.py is deleted and cannot be imported."""
        path = Path("CyberScoutAI/src/intelligence/query_builder.py")
        if not path.exists():
            path = Path("src/intelligence/query_builder.py")
        self.assertFalse(path.exists(), "src/intelligence/query_builder.py must be physically deleted")

        with self.assertRaises(ModuleNotFoundError):
            import src.intelligence.query_builder  # noqa: F401

    def test_03_template_engine_physically_deleted(self):
        """Verify template_engine.py is deleted and cannot be imported."""
        path = Path("CyberScoutAI/src/intelligence/template_engine.py")
        if not path.exists():
            path = Path("src/intelligence/template_engine.py")
        self.assertFalse(path.exists(), "src/intelligence/template_engine.py must be physically deleted")

        with self.assertRaises(ModuleNotFoundError):
            import src.intelligence.template_engine  # noqa: F401

    def test_04_query_validator_physically_deleted(self):
        """Verify query_validator.py is deleted and cannot be imported."""
        path = Path("CyberScoutAI/src/intelligence/query_validator.py")
        if not path.exists():
            path = Path("src/intelligence/query_validator.py")
        self.assertFalse(path.exists(), "src/intelligence/query_validator.py must be physically deleted")

        with self.assertRaises(ModuleNotFoundError):
            import src.intelligence.query_validator  # noqa: F401

    def test_05_html_collector_physically_deleted(self):
        """Verify html_collector.py is deleted and cannot be imported."""
        path = Path("CyberScoutAI/src/collectors/html_collector.py")
        if not path.exists():
            path = Path("src/collectors/html_collector.py")
        self.assertFalse(path.exists(), "src/collectors/html_collector.py must be physically deleted")

        with self.assertRaises(ModuleNotFoundError):
            import src.collectors.html_collector  # noqa: F401

    def test_06_no_obsolete_modules_in_intelligence_package_export(self):
        """Verify obsolete search modules are excluded from src.intelligence package."""
        obsolete_names = [
            "SearchPlanner",
            "QueryBuilder",
            "SearchTemplateEngine",
            "QueryValidator",
        ]
        for name in obsolete_names:
            self.assertFalse(
                hasattr(src.intelligence, name),
                f"Obsolete class '{name}' must not be exported by src.intelligence",
            )
            self.assertNotIn(
                name,
                src.intelligence.__all__,
                f"Obsolete class '{name}' must not be in src.intelligence.__all__",
            )

    def test_07_collector_registry_does_not_contain_html_scraper(self):
        """Verify CollectorRegistry does not register HtmlScraperCollector."""
        reg = src.collectors.registry.CollectorRegistry()
        collectors = reg.list_collectors()
        self.assertNotIn("HtmlScraperCollector", collectors)

    def test_08_search_templates_yaml_removed_from_disk(self):
        """Verify config/search_templates.yaml is permanently deleted."""
        templates_path = Path("CyberScoutAI/config/search_templates.yaml")
        if not templates_path.exists():
            templates_path = Path("config/search_templates.yaml")
        self.assertFalse(
            templates_path.exists(),
            "config/search_templates.yaml must be deleted from repository",
        )

    def test_09_tavily_discovery_is_active_provider_in_pipeline(self):
        """Verify GlobalDiscoveryService (Tavily) is invoked by run_pipeline_once."""
        mock_discovery = MagicMock(spec=GlobalDiscoveryService)
        mock_discovery.run_discovery.return_value = DiscoveryRunSummary(
            run_id="disc-test-b1",
            started_at=datetime.now(timezone.utc).isoformat(),
            candidates_found_raw=12,
            candidates_valid=10,
            status="completed",
        )

        res = run_pipeline_once(
            dry_run=True,
            db_manager=self.db_manager,
            discovery_service=mock_discovery,
        )

        mock_discovery.run_discovery.assert_called_once()
        self.assertEqual(res["status"], "success")
        self.assertIn("discovery_summary", res)
        self.assertEqual(res["discovery_summary"]["candidates_valid"], 10)

    def test_10_tavily_failure_does_not_trigger_legacy_fallback(self):
        """Verify failure of Tavily discovery logs error and NEVER falls back to old discovery."""
        mock_discovery = MagicMock(spec=GlobalDiscoveryService)
        mock_discovery.run_discovery.side_effect = RuntimeError("Tavily API quota exceeded")

        res = run_pipeline_once(
            dry_run=True,
            db_manager=self.db_manager,
            discovery_service=mock_discovery,
        )

        mock_discovery.run_discovery.assert_called_once()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["items_collected"], 0)

    def test_11_pipeline_rejects_legacy_search_planner_parameter(self):
        """Verify passing search_planner to pipeline raises explicit RuntimeError."""
        dummy = MagicMock()
        with self.assertRaises(RuntimeError) as ctx1:
            run_pipeline_once(
                dry_run=True,
                db_manager=self.db_manager,
                search_planner=dummy,
            )
        self.assertIn("SearchPlanner has been permanently decommissioned", str(ctx1.exception))

        with self.assertRaises(RuntimeError) as ctx2:
            PipelineRunner(
                db_manager=self.db_manager,
                search_planner=dummy,
            )
        self.assertIn("SearchPlanner has been permanently decommissioned", str(ctx2.exception))

    def test_12_staged_candidates_stored_with_correct_attributes(self):
        """Verify discovered candidates have proper status and audit metadata."""
        candidate = DiscoveredCandidate(
            discovery_run_id="run-audit-1",
            search_query="cybersecurity internships India 2026",
            search_provider="tavily",
            original_url="https://internshala.com/internship/detail/security-intern-101",
            canonical_url="https://internshala.com/internship/detail/security-intern-101",
            url_hash="hash-101",
            title="Cybersecurity Research Intern",
            snippet="Exciting remote cybersecurity internship in India.",
            source_domain="internshala.com",
            platform_name="Internshala",
            country_or_scope="India",
            category=OpportunityCategory.INTERNSHIP.value,
            processing_status=CandidateProcessingStatus.DISCOVERED.value,
            pricing_verification_status=PricingVerificationStatus.UNCERTAIN.value,
        )
        as_dict = candidate.to_dict()
        self.assertEqual(as_dict["search_provider"], "tavily")
        self.assertEqual(as_dict["country_or_scope"], "India")
        self.assertEqual(as_dict["processing_status"], "discovered")
        self.assertEqual(as_dict["pricing_verification_status"], "UNCERTAIN")
        self.assertEqual(as_dict["platform_name"], "Internshala")
        self.assertEqual(as_dict["url_hash"], "hash-101")

    def test_13_unvetted_candidates_isolated_from_production_opportunities(self):
        """Verify Tavily staged candidates do NOT enter production Opportunities table directly."""
        mock_discovery = MagicMock(spec=GlobalDiscoveryService)
        mock_discovery.run_discovery.return_value = DiscoveryRunSummary(
            run_id="disc-isolate-1",
            started_at=datetime.now(timezone.utc).isoformat(),
            candidates_found_raw=3,
            candidates_valid=3,
            status="completed",
        )

        res = run_pipeline_once(
            dry_run=True,
            db_manager=self.db_manager,
            discovery_service=mock_discovery,
        )

        self.assertEqual(res["discovery_summary"]["candidates_valid"], 3)
        self.assertEqual(res["items_collected"], 0)
        self.assertEqual(res["saved"], 0)

    def test_14_useful_taxonomies_preserved(self):
        """Verify critical taxonomies, platforms, and regions remain active."""
        plat_reg = PlatformRegistry()
        self.assertIsNotNone(plat_reg.get_platform_by_id("linkedin"))
        self.assertIsNotNone(plat_reg.get_platform_by_id("internshala"))
        self.assertIsNotNone(plat_reg.get_platform_by_id("hackerone"))

        self.assertIn(GeographicRegion.INDIA, RegionRegistry.REGION_KEYWORDS)
        detected = RegionRegistry.detect_region("Cybersecurity internship in Bengaluru", "example.in")
        self.assertEqual(detected, GeographicRegion.INDIA)

        taxonomy_cfg = {
            "categories": {
                "offensive_security": ["pentest", "ctf"],
                "defensive_security": ["soc", "siem"],
            }
        }
        tax = KeywordTaxonomy(keywords_config=taxonomy_cfg)
        tags = tax.match_tags("Free SOC analyst internship and SIEM workshop")
        self.assertIn("defensive_security", tags)
        self.assertIn("soc", tags)
        self.assertIn("siem", tags)

        src_reg = SourceRegistry()
        self.assertGreater(len(src_reg.get_all_sources()), 0)


if __name__ == "__main__":
    unittest.main()
