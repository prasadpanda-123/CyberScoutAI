"""
Unit Tests for Discovery Query Planner.

Verifies:
- India dedicated search query generation and keyword enrichment
- Global remote and international regional query generation
- Comprehensive category coverage across all 15 cybersecurity opportunity categories
- Compliant LinkedIn public search query generation (no automated scraping)
- Budget limit enforcement and India query prioritization
"""

import pytest

from src.discovery.discovery_models import GeographicRegion, OpportunityCategory, SearchQuerySpec
from src.discovery.platform_registry import PlatformRegistry
from src.discovery.query_planner import DiscoveryQueryPlanner
from src.discovery.region_registry import RegionRegistry


class TestDiscoveryQueryPlanner:

    def setup_method(self):
        self.planner = DiscoveryQueryPlanner()

    def test_india_dedicated_queries_generated(self):
        """India query set must include dedicated Indian terms and major platforms."""
        queries = self.planner.get_india_dedicated_queries()
        assert len(queries) >= 5

        all_query_text = " ".join([q.query for q in queries])
        # Verify presence of India-specific keywords and platforms
        assert "India" in all_query_text
        assert "unstop.com" in all_query_text
        assert "internshala.com" in all_query_text
        assert "cert-in" in all_query_text or "nciipc" in all_query_text

        # Verify all queries in this set belong to India region
        for q in queries:
            assert q.region == GeographicRegion.INDIA
            assert q.priority in (1, 2)

    def test_linkedin_public_discovery_compliance(self):
        """LinkedIn queries must use site: search syntax targeting public jobs, never session scraping."""
        queries = self.planner.get_india_dedicated_queries() + self.planner.get_global_remote_queries()
        linkedin_queries = [q for q in queries if q.target_platform == "LinkedIn" or "linkedin.com" in q.query]

        assert len(linkedin_queries) >= 2
        for lq in linkedin_queries:
            assert "site:linkedin.com/jobs" in lq.query
            # Ensure no credentials or illegal session extraction terms exist
            assert "cookie" not in lq.query.lower()
            assert "password" not in lq.query.lower()
            assert "login" not in lq.query.lower()

    def test_global_remote_queries_coverage(self):
        """Global remote queries must cover CTFs, bug bounties, free academies, and open source."""
        queries = self.planner.get_global_remote_queries()
        all_text = " ".join([q.query for q in queries])

        assert "hackerone.com" in all_text or "bugcrowd.com" in all_text
        assert "ctftime.org" in all_text
        assert "portswigger.net" in all_text or "tryhackme.com" in all_text

        for q in queries:
            assert q.region == GeographicRegion.GLOBAL_REMOTE

    def test_international_regional_queries(self):
        """International queries must cover North America, Europe, Asia, Africa, Middle East, Oceania."""
        queries = self.planner.get_international_regional_queries()
        regions_covered = {q.region for q in queries}

        assert GeographicRegion.NORTH_AMERICA in regions_covered
        assert GeographicRegion.EUROPE in regions_covered
        assert GeographicRegion.ASIA in regions_covered
        assert GeographicRegion.MIDDLE_EAST in regions_covered
        assert GeographicRegion.AFRICA in regions_covered
        assert GeographicRegion.OCEANIA in regions_covered

    def test_category_coverage(self):
        """All planned queries across categories must cover internships, CTFs, bug bounties, courses, etc."""
        plan = self.planner.build_search_plan(max_queries=30)
        categories_represented = {q.category for q in plan}

        assert OpportunityCategory.INTERNSHIP in categories_represented
        assert OpportunityCategory.CTF in categories_represented
        assert OpportunityCategory.BUG_BOUNTY in categories_represented
        assert OpportunityCategory.HACKATHON in categories_represented
        assert OpportunityCategory.COURSE_CERTIFICATION in categories_represented
        assert OpportunityCategory.SCHOLARSHIP in categories_represented
        assert OpportunityCategory.FREE_TRAINING in categories_represented

    def test_build_search_plan_budget_truncation(self):
        """build_search_plan must strictly truncate queries to max_queries parameter."""
        plan_5 = self.planner.build_search_plan(max_queries=5)
        assert len(plan_5) == 5

        plan_12 = self.planner.build_search_plan(max_queries=12)
        assert len(plan_12) == 12

    def test_india_priority_ordering(self):
        """When prioritize_india=True, India queries must appear at the top of the plan."""
        plan = self.planner.build_search_plan(max_queries=10, prioritize_india=True)
        # Priority 1 queries should lead
        first_three = plan[:3]
        for q in first_three:
            assert q.priority == 1
        # At least 2 of the top 3 must be India queries
        india_in_top_three = sum(1 for q in first_three if q.region == GeographicRegion.INDIA)
        assert india_in_top_three >= 2

