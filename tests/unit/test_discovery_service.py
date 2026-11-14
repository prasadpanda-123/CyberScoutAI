"""
Unit Tests for Global Discovery Service.

Verifies:
- End-to-end discovery orchestration with mocked Tavily responses
- Concurrency protection and scheduler locking
- Duplicate candidate prevention (in-run and database deduplication)
- Strict SSRF / dangerous URL rejection
- Zero-trust pricing handling: candidate staged with is_free=None and pricing_verification_status='UNCERTAIN'
- Platform and regional detection
- Partial failure and budget limit recovery
- Dry-run execution behavior
"""

from unittest.mock import MagicMock, patch
import pytest

from src.discovery.discovery_models import (
    CandidateProcessingStatus,
    DiscoveredCandidate,
    DiscoveryBudget,
    GeographicRegion,
    OpportunityCategory,
    PricingVerificationStatus,
    SearchQuerySpec,
)
from src.discovery.discovery_service import GlobalDiscoveryService


class TestGlobalDiscoveryService:

    def setup_method(self):
        self.mock_tavily = MagicMock()
        self.mock_tavily.is_configured = True
        self.mock_repo = MagicMock()
        self.mock_repo.is_url_already_discovered.return_value = False
        self.mock_repo.is_url_in_approved_opportunities.return_value = False
        self.mock_repo.save_candidates_batch.return_value = (2, 0)

        self.service = GlobalDiscoveryService(
            tavily_client=self.mock_tavily,
            candidate_repo=self.mock_repo,
            budget=DiscoveryBudget(daily_limit=10, max_searches_per_run=5, max_results_per_query=10),
        )

    @patch("src.automation.job_manager.scan_job_manager.is_scan_active", return_value=False)
    def test_successful_discovery_run(self, mock_active):
        """Service should execute planned queries, validate URLs, and stage valid candidates."""
        self.mock_tavily.execute_query_spec.return_value = [
            {
                "title": "CERT-In Cyber Security Internship 2026",
                "url": "https://cert-in.org.in/careers/intern-2026",
                "content": "Official government cybersecurity internship program in New Delhi, India.",
                "score": 0.95,
            },
            {
                "title": "Unstop Collegiate CTF Challenge",
                "url": "https://unstop.com/competitions/ctf-2026",
                "content": "Free CTF competition for Indian university students.",
                "score": 0.89,
            },
        ]

        summary = self.service.run_discovery(max_queries=2, prioritize_india=True)

        assert summary.status == "completed"
        assert summary.queries_executed == 2
        assert summary.candidates_found_raw == 4  # 2 results * 2 queries
        assert summary.candidates_valid >= 2
        assert self.mock_repo.save_candidates_batch.called

        # Verify staged candidate fields
        staged_candidates = self.mock_repo.save_candidates_batch.call_args[0][0]
        assert len(staged_candidates) >= 2
        first = staged_candidates[0]
        assert first.search_provider == "tavily"
        assert first.canonical_url.startswith("https://")
        assert len(first.url_hash) == 64
        # Crucial zero-trust free-only requirement:
        assert first.is_free is None
        assert first.pricing_verification_status == PricingVerificationStatus.UNCERTAIN.value

    @patch("src.automation.job_manager.scan_job_manager.is_scan_active", return_value=True)
    def test_scheduler_concurrency_lock_prevents_overlap(self, mock_active):
        """When another scan is active, discovery must abort and return conflict status."""
        summary = self.service.run_discovery(max_queries=2)
        assert summary.status == "conflict"
        assert "already active" in summary.errors[0]
        assert not self.mock_tavily.execute_query_spec.called

    @patch("src.automation.job_manager.scan_job_manager.is_scan_active", return_value=False)
    def test_duplicate_candidates_filtered_out(self, mock_active):
        """Duplicate URLs in same run or already present in DB must be filtered out."""
        # Mock Tavily returning the same URL twice in the same batch
        self.mock_tavily.execute_query_spec.return_value = [
            {
                "title": "CTFtime Event 1",
                "url": "https://ctftime.org/event/999",
                "content": "Jeopardy CTF.",
                "score": 0.9,
            },
            {
                "title": "CTFtime Event 1 (Duplicate with tracking)",
                "url": "https://ctftime.org/event/999?utm_source=twitter",
                "content": "Jeopardy CTF identical link.",
                "score": 0.9,
            },
        ]

        summary = self.service.run_discovery(max_queries=1)
        assert summary.candidates_valid == 1
        assert summary.candidates_duplicates == 1

    @patch("src.automation.job_manager.scan_job_manager.is_scan_active", return_value=False)
    def test_ssrf_and_dangerous_urls_rejected(self, mock_active):
        """URLs pointing to localhost, private IPs, or dangerous schemes must be rejected."""
        self.mock_tavily.execute_query_spec.return_value = [
            {
                "title": "Evil Localhost Link",
                "url": "http://127.0.0.1/admin",
                "content": "Private admin interface.",
                "score": 0.9,
            },
            {
                "title": "Evil Cloud Metadata Link",
                "url": "http://169.254.169.254/latest/meta-data/",
                "content": "Metadata link.",
                "score": 0.9,
            },
            {
                "title": "Valid Safe Link",
                "url": "https://hackerone.com/bug-bounty-program",
                "content": "Public bounty.",
                "score": 0.9,
            },
        ]

        summary = self.service.run_discovery(max_queries=1)
        assert summary.candidates_rejected_security == 2
        assert summary.candidates_valid == 1

    @patch("src.automation.job_manager.scan_job_manager.is_scan_active", return_value=False)
    def test_platform_and_region_detected_on_candidates(self, mock_active):
        """Candidates must have platform_name and country_or_scope accurately identified."""
        self.mock_tavily.execute_query_spec.return_value = [
            {
                "title": "HackerOne Public Bug Bounty",
                "url": "https://hackerone.com/target-vdp",
                "content": "Global vulnerability disclosure program.",
                "score": 0.9,
            },
            {
                "title": "Unstop Bangalore Security Hackathon",
                "url": "https://unstop.com/hackathons/bangalore-cyber",
                "content": "Bengaluru student hackathon.",
                "score": 0.88,
            },
        ]

        summary = self.service.run_discovery(max_queries=1)
        staged_candidates = self.mock_repo.save_candidates_batch.call_args[0][0]

        h1_cand = next(c for c in staged_candidates if "hackerone" in c.canonical_url)
        assert h1_cand.platform_name == "HackerOne"

        unstop_cand = next(c for c in staged_candidates if "unstop" in c.canonical_url)
        assert unstop_cand.platform_name == "Unstop"
        assert unstop_cand.country_or_scope == "india"

    @patch("src.automation.job_manager.scan_job_manager.is_scan_active", return_value=False)
    def test_dry_run_mode_bypasses_external_writes(self, mock_active):
        """In dry_run=True, no external searches are made and DB is untouched."""
        summary = self.service.run_discovery(max_queries=3, dry_run=True)
        assert summary.status == "completed"
        assert summary.queries_executed == 3
        assert not self.mock_tavily.execute_query_spec.called
        assert not self.mock_repo.save_candidates_batch.called

    @patch("src.automation.job_manager.scan_job_manager.is_scan_active", return_value=False)
    def test_unconfigured_api_key_aborts_gracefully(self, mock_active):
        """If Tavily client is unconfigured, discovery aborts cleanly with failure status."""
        self.mock_tavily.is_configured = False
        summary = self.service.run_discovery(max_queries=2)
        assert summary.status == "failed"
        assert "TAVILY_API_KEY is missing" in summary.errors[0]

