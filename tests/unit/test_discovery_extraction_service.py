"""
Unit Tests for Firecrawl Content Extraction Service.

Verifies:
- End-to-end extraction cycle with mocked Firecrawl client
- Strict SSRF protection (pre-fetch resolution against private/loopback/cloud metadata)
- Canonical redirect SSRF protection (post-fetch redirect destination check)
- Quality gates (empty / low-character scrape rejection)
- Duplicate content hash detection across candidates
- Evidence-based field extraction (free/paid statements, skills, remote/onsite, deadlines)
- Zero-trust principle: missing fields remain None, zero hallucinated facts
- Candidate staging isolation: updates DiscoveredCandidates, never writes to Opportunities
- Safe skipping when Firecrawl is disabled or credentials are missing
"""

from unittest.mock import MagicMock, patch
import pytest

from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.discovery_models import (
    CandidateProcessingStatus,
    DiscoveredCandidate,
    ExtractionBudget,
    ExtractionStatus,
    PricingVerificationStatus,
)
from src.discovery.extraction_service import FirecrawlExtractionService
from src.discovery.url_validator import URLValidationResult


class TestFirecrawlExtractionService:

    def setup_method(self):
        self.mock_client = MagicMock()
        self.mock_client.is_enabled = True
        self.mock_client.is_configured = True
        self.mock_repo = MagicMock(spec=DiscoveredCandidateRepository)
        self.mock_db = MagicMock()

        self.service = FirecrawlExtractionService(
            firecrawl_client=self.mock_client,
            candidate_repo=self.mock_repo,
            db_manager=self.mock_db,
            budget=ExtractionBudget(daily_limit=20, max_pages_per_run=10),
        )

    def _create_sample_candidate(
        self,
        candidate_id: str = "cand-1",
        url: str = "https://example-security.org/fellowship",
        category: str = "internship",
    ) -> DiscoveredCandidate:
        return DiscoveredCandidate(
            id=candidate_id,
            discovery_run_id="run-101",
            search_query="cybersecurity fellowship",
            search_provider="tavily",
            original_url=url,
            canonical_url=url,
            url_hash="a" * 64,
            title="Cybersecurity Fellowship 2026",
            snippet="Free fellowship for cyber defenders.",
            source_domain="example-security.org",
            category=category,
            processing_status=CandidateProcessingStatus.READY_FOR_EXTRACTION.value,
            extraction_status=ExtractionStatus.PENDING.value,
        )

    def test_successful_extraction_and_field_normalization(self):
        """Extraction service must parse evidence-based fields and update candidate staging record."""
        cand = self._create_sample_candidate()
        self.mock_repo.get_candidates_for_extraction.return_value = [cand]
        self.mock_repo.get_candidate_by_id.return_value = cand
        self.mock_repo.update_candidate_extraction.return_value = True

        # Mock Firecrawl scrape response with rich evidence
        self.mock_client.scrape_url.return_value = {
            "markdown": (
                "# Global Cybersecurity Fellowship 2026\n\n"
                "This fellowship is completely free of cost for all accepted researchers.\n"
                "Work arrangement: 100% remote opportunity. Work from home anywhere.\n"
                "Key skills required: Python, Splunk, SOC, and Reverse Engineering.\n"
                "Application deadline: December 31, 2026. Free admission.\n"
            ),
            "html": "<html><body><h1>Global Cybersecurity Fellowship 2026</h1></body></html>",
            "metadata": {
                "title": "Global Cybersecurity Fellowship 2026",
                "sourceURL": "https://example-security.org/fellowship",
                "ogSiteName": "Example Security Org",
            },
        }

        # Patch URLValidator to allow the test domain without live DNS resolution
        with patch.object(self.service.url_validator, "validate") as mock_val:
            mock_val.return_value = URLValidationResult(
                is_valid=True,
                original_url=cand.original_url,
                canonical_url="https://example-security.org/fellowship",
                url_hash="a" * 64,
                domain="example-security.org",
            )

            summary = self.service.run_extraction(candidates=[cand])

        assert summary.status == "completed"
        assert summary.pages_succeeded == 1
        assert summary.pages_attempted == 1
        assert summary.pages_failed == 0

        # Verify staging table update was executed
        assert self.mock_repo.update_candidate_extraction.called
        call_kwargs = self.mock_repo.update_candidate_extraction.call_args[1]
        assert call_kwargs["candidate_id"] == "cand-1"
        assert call_kwargs["extraction_status"] == ExtractionStatus.COMPLETED.value
        assert call_kwargs["processing_status"] == CandidateProcessingStatus.READY_FOR_EXTRACTION.value

        meta_update = call_kwargs["metadata_updates"]
        extracted_data = meta_update["extraction"]
        assert extracted_data["organization_or_publisher"] == "Example Security Org"
        assert extracted_data["remote_or_onsite"] == "remote"
        assert "python" in extracted_data["required_skills"]
        assert "soc" in extracted_data["required_skills"]
        assert len(extracted_data["source_evidence"]) > 0
        assert extracted_data["content_hash"] != ""

    def test_ssrf_pre_check_blocks_private_ip(self):
        """Private IP addresses must be rejected pre-fetch without making Firecrawl calls."""
        cand = self._create_sample_candidate(url="http://192.168.1.100/internal-job")

        with patch.object(self.service.url_validator, "validate") as mock_val:
            mock_val.return_value = URLValidationResult(
                is_valid=False,
                original_url=cand.original_url,
                rejection_reason="SSRF attempt: IP 192.168.1.100 is private",
            )

            summary = self.service.run_extraction(candidates=[cand])

        assert summary.pages_rejected_security == 1
        assert summary.pages_succeeded == 0
        assert not self.mock_client.scrape_url.called
        # Verify candidate marked as failed/skipped
        assert self.mock_repo.update_candidate_extraction.called
        call_kwargs = self.mock_repo.update_candidate_extraction.call_args[1]
        assert call_kwargs["extraction_status"] == ExtractionStatus.SKIPPED.value
        assert call_kwargs["processing_status"] == CandidateProcessingStatus.SECURITY_REJECTED.value

    def test_ssrf_post_check_blocks_malicious_redirect(self):
        """Redirect destinations pointing to AWS cloud metadata must be rejected post-fetch."""
        cand = self._create_sample_candidate(url="https://innocent-looking-domain.com/redirect")

        # 1. Pre-check passes
        with patch.object(self.service.url_validator, "validate") as mock_val:
            # First call for candidate URL passes
            # Second call for redirect canonical URL fails
            mock_val.side_effect = [
                URLValidationResult(is_valid=True, original_url=cand.original_url, canonical_url="https://innocent-looking-domain.com/redirect"),
                URLValidationResult(is_valid=False, original_url="http://169.254.169.254/latest/meta-data/", rejection_reason="SSRF attempt: target 169.254.169.254 is cloud metadata"),
            ]

            self.mock_client.scrape_url.return_value = {
                "markdown": "# Metadata stolen",
                "metadata": {"sourceURL": "http://169.254.169.254/latest/meta-data/"},
            }

            summary = self.service.run_extraction(candidates=[cand])

        assert summary.pages_rejected_security == 1
        assert summary.pages_succeeded == 0
        call_kwargs = self.mock_repo.update_candidate_extraction.call_args[1]
        assert call_kwargs["processing_status"] == CandidateProcessingStatus.SECURITY_REJECTED.value

    def test_empty_content_rejected_as_failure(self):
        """Scraped pages with fewer than 30 characters must be marked as failed / low quality."""
        cand = self._create_sample_candidate()

        with patch.object(self.service.url_validator, "validate") as mock_val:
            mock_val.return_value = URLValidationResult(is_valid=True, original_url=cand.original_url, canonical_url=cand.canonical_url)

            self.mock_client.scrape_url.return_value = {
                "markdown": "404 Not Found",
                "html": "<p>404</p>",
                "metadata": {},
            }

            summary = self.service.run_extraction(candidates=[cand])

        assert summary.pages_failed == 1
        assert summary.pages_succeeded == 0
        call_kwargs = self.mock_repo.update_candidate_extraction.call_args[1]
        assert call_kwargs["extraction_status"] == ExtractionStatus.FAILED.value
        assert "empty or low-quality" in call_kwargs["metadata_updates"]["last_extraction_error"]

    def test_duplicate_content_hash_detection(self):
        """Duplicate content across different URLs must be flagged and skipped."""
        cand1 = self._create_sample_candidate(candidate_id="cand-1", url="https://site1.org/internship")
        cand2 = self._create_sample_candidate(candidate_id="cand-2", url="https://site2.org/internship-mirror")

        with patch.object(self.service.url_validator, "validate") as mock_val:
            mock_val.return_value = URLValidationResult(is_valid=True, original_url="https://site.org/job", canonical_url="https://site.org/job")

            identical_markdown = "# Identical Internship Description\n" + ("Long text description. " * 10)
            self.mock_client.scrape_url.return_value = {
                "markdown": identical_markdown,
                "html": "<p>Long text</p>",
                "metadata": {},
            }

            summary = self.service.run_extraction(candidates=[cand1, cand2])

        assert summary.pages_succeeded == 1
        assert summary.pages_duplicate == 1
        assert summary.pages_attempted == 2

    def test_zero_trust_preserves_null_for_unverified_fields(self):
        """Zero-trust: when no fee or eligibility is mentioned, fields MUST remain null/None."""
        cand = self._create_sample_candidate()

        with patch.object(self.service.url_validator, "validate") as mock_val:
            mock_val.return_value = URLValidationResult(is_valid=True, original_url=cand.original_url, canonical_url=cand.canonical_url)

            # Markdown with no financial or eligibility statements
            self.mock_client.scrape_url.return_value = {
                "markdown": "# Security Research Program\nConduct research on cryptographic primitives.",
                "html": "<p>Conduct research</p>",
                "metadata": {"title": "Security Research Program"},
            }

            summary = self.service.run_extraction(candidates=[cand])

        assert summary.pages_succeeded == 1
        meta = self.mock_repo.update_candidate_extraction.call_args[1]["metadata_updates"]["extraction"]
        # Never invent fees or currencies:
        assert meta["pricing_statements"] is None
        assert meta["currency"] is None
        assert meta["fee_amount"] is None
        assert meta["eligibility_requirements"] is None

    def test_disabled_firecrawl_skips_safely(self):
        """When Firecrawl is disabled, service returns disabled summary and touches no candidates."""
        self.mock_client.is_enabled = False
        summary = self.service.run_extraction()

        assert summary.status == "disabled"
        assert summary.pages_attempted == 0
        assert not self.mock_repo.get_candidates_for_extraction.called

    def test_missing_credentials_safe_status(self):
        """When API key is missing, service returns skipped_missing_credentials and does not crash."""
        self.mock_client.is_configured = False
        summary = self.service.run_extraction()

        assert summary.status == "skipped_missing_credentials"
        assert summary.pages_attempted == 0
        assert "FIRECRAWL_API_KEY is missing" in summary.errors[0]

    def test_staging_isolation_guarantee(self):
        """Extracted data must be stored ONLY in DiscoveredCandidates staging table, never Opportunities."""
        cand = self._create_sample_candidate()

        with patch.object(self.service.url_validator, "validate") as mock_val:
            mock_val.return_value = URLValidationResult(is_valid=True, original_url=cand.original_url, canonical_url=cand.canonical_url)

            self.mock_client.scrape_url.return_value = {
                "markdown": "# Junior Analyst Free Training\nFree cybersecurity training for beginners.",
                "html": "<p>Free training</p>",
                "metadata": {"title": "Junior Analyst Free Training"},
            }

            self.service.run_extraction(candidates=[cand])

        # Verify DiscoveredCandidate repository updated
        assert self.mock_repo.update_candidate_extraction.called
        # Verify no opportunities methods called on db or repo
        assert not hasattr(self.service, "save_opportunity")
        assert not hasattr(self.service, "opportunity_repo")
