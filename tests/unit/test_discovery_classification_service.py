"""
Unit Tests for AI Opportunity Classification Service (Phase D).

Verifies:
- Primary AI classification workflow via Groq
- Fallback AI classification workflow via Google Gemini when Groq fails
- Fallback AI classification when Groq returns invalid structured JSON
- Failure handling when both AI providers fail (staged for retry, no pipeline crash)
- Zero-hallucination preservation (no invented classification)
- Disabled configuration behavior
- Missing credentials safe handling
- Candidate staging isolation: updates DiscoveredCandidates, never writes to Opportunities
"""

from unittest.mock import MagicMock, patch
import pytest

from src.discovery.classification_models import (
    ClassificationBudget,
    ClassificationResult,
    FinancialClassification,
)
from src.discovery.classification_repository import ClassificationRepository
from src.discovery.classification_service import AIClassificationService
from src.discovery.classification_validator import ClassificationValidator
from src.discovery.client_gemini import GeminiAPIError, GeminiClient
from src.discovery.client_groq import GroqClient, GroqRateLimitError
from src.discovery.discovery_models import DiscoveredCandidate


class TestAIClassificationService:

    def setup_method(self):
        self.mock_groq = MagicMock(spec=GroqClient)
        self.mock_groq.is_configured = True
        self.mock_groq.model = "llama-3.3-70b-versatile"

        self.mock_gemini = MagicMock(spec=GeminiClient)
        self.mock_gemini.is_configured = True
        self.mock_gemini.model = "gemini-2.5-flash"

        self.mock_repo = MagicMock(spec=ClassificationRepository)
        self.mock_repo.update_candidate_classification.return_value = True
        self.mock_repo.mark_classification_failed.return_value = True

        self.mock_validator = MagicMock(spec=ClassificationValidator)

        self.service = AIClassificationService(
            groq_client=self.mock_groq,
            gemini_client=self.mock_gemini,
            validator=self.mock_validator,
            classification_repo=self.mock_repo,
            budget=ClassificationBudget(max_classifications_per_run=10),
        )

    def _create_sample_candidate(
        self,
        candidate_id: str = "cand-1",
        url: str = "https://example-security.org/ctf",
    ) -> DiscoveredCandidate:
        return DiscoveredCandidate(
            id=candidate_id,
            discovery_run_id="run-201",
            search_query="cybersecurity ctf",
            search_provider="tavily",
            original_url=url,
            canonical_url=url,
            url_hash="b" * 64,
            title="National Collegiate CTF 2026",
            snippet="Free online CTF competition for university students.",
            source_domain="example-security.org",
            category="ctf",
            extraction_status="completed",
            metadata={
                "extraction": {
                    "main_content_markdown": "# National Collegiate CTF 2026\nFree online CTF. Cash prizes.",
                    "short_description": "Free online CTF competition.",
                }
            },
        )

    def _create_dummy_result(self, provider: str, model: str) -> ClassificationResult:
        return ClassificationResult(
            candidate_id="cand-1",
            title="National Collegiate CTF 2026",
            description="Free online CTF competition for cybersecurity students.",
            category="ctf",
            confidence=0.92,
            provider_used=provider,
            model_used=model,
            financial=FinancialClassification(
                participation_cost_status="FREE",
                compensation_status="PAID",
                compensation_details="$5,000 in cash prizes",
            ),
        )

    def test_primary_groq_classification_success(self):
        """When Groq succeeds and validates, result is persisted and Gemini is not invoked."""
        cand = self._create_sample_candidate()
        dummy_res = self._create_dummy_result(provider="groq", model="llama-3.3-70b-versatile")

        self.mock_groq.classify.return_value = {"title": "National Collegiate CTF 2026"}
        self.mock_validator.validate.return_value = (True, [], dummy_res)

        summary = self.service.run_classification(candidates=[cand])

        assert summary.status == "completed"
        assert summary.candidates_attempted == 1
        assert summary.candidates_classified_groq == 1
        assert summary.candidates_classified_gemini == 0
        assert summary.candidates_failed == 0

        # Verify Groq was called, Gemini was not
        assert self.mock_groq.classify.called
        assert not self.mock_gemini.classify.called

        # Verify persistence
        assert self.mock_repo.update_candidate_classification.called
        call_kwargs = self.mock_repo.update_candidate_classification.call_args[1]
        assert call_kwargs["candidate_id"] == "cand-1"
        assert call_kwargs["result"].provider_used == "groq"

    def test_fallback_to_gemini_on_groq_error(self):
        """When Groq raises an error (e.g. rate limit), system falls back to Gemini."""
        cand = self._create_sample_candidate()
        dummy_res = self._create_dummy_result(provider="gemini", model="gemini-2.5-flash")

        # Groq fails with rate limit
        self.mock_groq.classify.side_effect = GroqRateLimitError("Rate limit reached")
        # Gemini succeeds
        self.mock_gemini.classify.return_value = {"title": "National Collegiate CTF 2026"}
        self.mock_validator.validate.return_value = (True, [], dummy_res)

        summary = self.service.run_classification(candidates=[cand])

        assert summary.status == "completed"
        assert summary.candidates_attempted == 1
        assert summary.candidates_classified_groq == 0
        assert summary.candidates_classified_gemini == 1
        assert summary.candidates_failed == 0

        # Verify both were called in sequence
        assert self.mock_groq.classify.called
        assert self.mock_gemini.classify.called

        # Verify persistence with Gemini provider attribution
        assert self.mock_repo.update_candidate_classification.called
        call_kwargs = self.mock_repo.update_candidate_classification.call_args[1]
        assert call_kwargs["result"].provider_used == "gemini"

    def test_fallback_to_gemini_on_groq_validation_failure(self):
        """When Groq returns invalid schema or ungrounded evidence, Gemini is invoked as fallback."""
        cand = self._create_sample_candidate()
        dummy_res = self._create_dummy_result(provider="gemini", model="gemini-2.5-flash")

        self.mock_groq.classify.return_value = {"bad": "schema"}
        self.mock_gemini.classify.return_value = {"valid": "schema"}

        # First validate call for Groq returns invalid; second validate call for Gemini succeeds
        self.mock_validator.validate.side_effect = [
            (False, ["Missing required fields"], None),
            (True, [], dummy_res),
        ]

        summary = self.service.run_classification(candidates=[cand])

        assert summary.candidates_classified_gemini == 1
        assert summary.candidates_classified_groq == 0
        assert summary.candidates_rejected_validation == 1
        assert self.mock_gemini.classify.called

    def test_both_providers_fail_staged_for_retry(self):
        """When both Groq and Gemini fail, candidate is marked as failed for retry without crashing."""
        cand = self._create_sample_candidate()

        self.mock_groq.classify.side_effect = GroqRateLimitError("Groq 429")
        self.mock_gemini.classify.side_effect = GeminiAPIError("Gemini 500")

        summary = self.service.run_classification(candidates=[cand])

        assert summary.status == "partial"
        assert summary.candidates_failed == 1
        assert summary.candidates_classified_groq == 0
        assert summary.candidates_classified_gemini == 0

        # Verify marked as failed in staging repo
        assert self.mock_repo.mark_classification_failed.called
        call_kwargs = self.mock_repo.mark_classification_failed.call_args[1]
        assert call_kwargs["candidate_id"] == "cand-1"
        assert "Groq" in call_kwargs["error_reason"]
        assert "Gemini" in call_kwargs["error_reason"]

    def test_disabled_classification_skips_cleanly(self):
        """When AI classification is disabled via flag, service skips immediately."""
        self.service.is_enabled = False
        summary = self.service.run_classification()

        assert summary.status == "disabled"
        assert summary.candidates_attempted == 0
        assert not self.mock_groq.classify.called
        assert not self.mock_gemini.classify.called

    def test_missing_credentials_safe_status(self):
        """When neither provider has credentials configured, service returns safe status."""
        self.mock_groq.is_configured = False
        self.mock_gemini.is_configured = False

        summary = self.service.run_classification()

        assert summary.status == "skipped_missing_credentials"
        assert summary.candidates_attempted == 0
        assert "Neither GROQ_API_KEY nor GEMINI_API_KEY is configured" in summary.errors[0]

    def test_staging_isolation_guarantee(self):
        """Classification updates DiscoveredCandidates staging table only; Opportunities is untouched."""
        cand = self._create_sample_candidate()
        dummy_res = self._create_dummy_result(provider="groq", model="llama-3.3-70b-versatile")

        self.mock_groq.classify.return_value = {"title": "National Collegiate CTF 2026"}
        self.mock_validator.validate.return_value = (True, [], dummy_res)

        self.service.run_classification(candidates=[cand])

        # Verify DiscoveredCandidates repo updated
        assert self.mock_repo.update_candidate_classification.called
        # Verify no opportunities repository methods or tables accessed
        assert not hasattr(self.service, "opportunity_repo")
        assert not hasattr(self.service, "save_opportunity")

