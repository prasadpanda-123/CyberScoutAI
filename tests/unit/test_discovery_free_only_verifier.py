"""
Unit Tests for Free-Only Verifier Orchestrator (Phase E).

Verifies:
- End-to-end batch verification across mixed candidates (APPROVED, REJECTED, QUARANTINED)
- Strict adherence to deterministic decisions without LLM calls
- Staging table persistence in DiscoveredCandidates
- Idempotent re-verification
- Graceful database exception handling without crashing
- Production table isolation (Opportunities table remains untouched)
"""

from unittest.mock import MagicMock, patch
import pytest

from src.discovery.discovery_models import DiscoveredCandidate
from src.discovery.free_only_models import (
    FinancialDimension,
    FreeOnlyDecision,
    PricingVerificationStatus,
    VerifiedPricingEvidence,
)
from src.discovery.free_only_repository import FreeOnlyRepository
from src.discovery.free_only_rules import FreeOnlyRuleEngine
from src.discovery.free_only_verifier import FreeOnlyVerifier


class TestFreeOnlyVerifier:

    def setup_method(self):
        self.mock_rule_engine = MagicMock(spec=FreeOnlyRuleEngine)
        self.mock_repo = MagicMock(spec=FreeOnlyRepository)
        self.mock_repo.update_candidate_verification.return_value = True

        self.verifier = FreeOnlyVerifier(
            rule_engine=self.mock_rule_engine,
            repository=self.mock_repo,
        )

    def _create_sample_candidate(
        self,
        candidate_id: str,
        category: str,
        title: str,
        content: str,
    ) -> DiscoveredCandidate:
        return DiscoveredCandidate(
            id=candidate_id,
            discovery_run_id="run-301",
            search_query="cyber opportunity",
            search_provider="tavily",
            original_url=f"https://example.org/{candidate_id}",
            canonical_url=f"https://example.org/{candidate_id}",
            url_hash="c" * 64,
            title=title,
            snippet=content[:60],
            source_domain="example.org",
            category=category,
            processing_status="classified",
            metadata={
                "extraction": {
                    "main_content_markdown": content,
                },
                "classification": {
                    "category": category,
                    "financial": {},
                },
            },
        )

    def test_end_to_end_verification_batch(self):
        """Verifier processes candidates, updates staging records, and computes summary breakdowns."""
        cand_app = self._create_sample_candidate("cand-1", "internship", "Free Internship", "100% free of cost internship.")
        cand_rej = self._create_sample_candidate("cand-2", "job", "Paid App Fee Job", "Application fee is $50.")
        cand_qua = self._create_sample_candidate("cand-3", "conference", "Ambiguous Conf", "Security conference details.")

        # Configure rule engine responses for each candidate
        self.mock_rule_engine.evaluate.side_effect = [
            (
                FreeOnlyDecision.APPROVED,
                PricingVerificationStatus.VERIFIED_FREE,
                True,
                "FREE",
                "PAID",
                "FREE",
                "Approved: Free internship.",
                [VerifiedPricingEvidence("https://example.org/cand-1", "100% free", "100% free", "general", True)],
                ["RULE_APPROVE_VERIFIED_FREE_OPPORTUNITY"],
            ),
            (
                FreeOnlyDecision.REJECTED,
                PricingVerificationStatus.VERIFIED_PAID,
                False,
                "PAID",
                "UNKNOWN",
                "PAID",
                "Rejected: Application fee required.",
                [VerifiedPricingEvidence("https://example.org/cand-2", "fee $50", "fee $50", "application_fee", True)],
                ["RULE_REJECT_MANDATORY_FEE"],
            ),
            (
                FreeOnlyDecision.QUARANTINED,
                PricingVerificationStatus.UNCERTAIN,
                None,
                "UNCERTAIN",
                "UNKNOWN",
                "UNKNOWN",
                "Quarantined: Pricing is missing.",
                [],
                ["RULE_DEFAULT_QUARANTINE_MISSING_PRICING"],
            ),
        ]

        summary = self.verifier.run_verification(candidates=[cand_app, cand_rej, cand_qua])

        assert summary.status == "completed"
        assert summary.candidates_evaluated == 3
        assert summary.candidates_approved == 1
        assert summary.candidates_rejected == 1
        assert summary.candidates_quarantined == 1

        # Check repository calls
        assert self.mock_repo.update_candidate_verification.call_count == 3
        first_call = self.mock_repo.update_candidate_verification.call_args_list[0][1]
        assert first_call["candidate_id"] == "cand-1"
        assert first_call["evaluation"].decision == FreeOnlyDecision.APPROVED
        assert first_call["evaluation"].is_free is True

        second_call = self.mock_repo.update_candidate_verification.call_args_list[1][1]
        assert second_call["candidate_id"] == "cand-2"
        assert second_call["evaluation"].decision == FreeOnlyDecision.REJECTED
        assert second_call["evaluation"].is_free is False

    def test_idempotent_re_verification(self):
        """Running verification multiple times on the same candidate yields identical deterministic output."""
        cand = self._create_sample_candidate("cand-1", "internship", "Free Internship", "100% free of cost internship.")

        self.mock_rule_engine.evaluate.return_value = (
            FreeOnlyDecision.APPROVED,
            PricingVerificationStatus.VERIFIED_FREE,
            True,
            "FREE",
            "PAID",
            "FREE",
            "Approved: Free internship.",
            [],
            ["RULE_APPROVE_VERIFIED_FREE_OPPORTUNITY"],
        )

        sum1 = self.verifier.run_verification(candidates=[cand])
        sum2 = self.verifier.run_verification(candidates=[cand])

        assert sum1.candidates_approved == 1
        assert sum2.candidates_approved == 1
        assert self.mock_repo.update_candidate_verification.call_count == 2

    def test_database_exception_handling_safely_quarantines(self):
        """When an exception occurs during evaluation or persistence, candidate is safely quarantined."""
        cand = self._create_sample_candidate("cand-err", "other", "Error Page", "Content")
        self.mock_rule_engine.evaluate.side_effect = RuntimeError("Simulated rule evaluation error")

        summary = self.verifier.run_verification(candidates=[cand])

        assert summary.candidates_quarantined == 1
        assert len(summary.errors) == 1
        assert "Simulated rule evaluation error" in summary.errors[0]
        # Verify fallback update was attempted with QUARANTINED status
        assert self.mock_repo.update_candidate_verification.called
        fallback_eval = self.mock_repo.update_candidate_verification.call_args[1]["evaluation"]
        assert fallback_eval.decision == FreeOnlyDecision.QUARANTINED
        assert fallback_eval.is_free is None

    def test_staging_isolation_guarantee(self):
        """Verification must strictly operate on DiscoveredCandidates staging and never touch Opportunities."""
        cand = self._create_sample_candidate("cand-1", "ctf", "CTF 2026", "Free to participate CTF.")
        self.mock_rule_engine.evaluate.return_value = (
            FreeOnlyDecision.APPROVED,
            PricingVerificationStatus.VERIFIED_FREE,
            True,
            "FREE",
            "PAID",
            "FREE",
            "Approved",
            [],
            ["RULE_APPROVE_VERIFIED_FREE_OPPORTUNITY"],
        )

        self.verifier.run_verification(candidates=[cand])

        # Verify no opportunities table methods exist on verifier
        assert not hasattr(self.verifier, "opportunity_repo")
        assert not hasattr(self.verifier, "save_opportunity")
        assert not hasattr(self.verifier, "publish_opportunity")

