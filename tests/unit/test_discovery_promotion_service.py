"""
Unit Tests for Phase F Controlled Production Promotion Service.
"""

from datetime import datetime, timedelta, timezone
import json
import pytest

from src.discovery.promotion_models import PromotionDecision, PromotionStatus
from src.discovery.promotion_service import ProductionPromotionService
from src.models.opportunity import Opportunity


class MockPromotionRepository:
    """Mock repository for unit testing promotion service in isolation."""

    def __init__(self, candidates=None, existing_opps=None):
        self.candidates = candidates or []
        self.existing_opps = existing_opps or []
        self.promoted_records = []
        self.marked_statuses = []

    def ensure_schema(self):
        return True

    def get_approved_candidates_for_promotion(self, run_id=None, limit=50):
        return self.candidates

    def get_existing_production_opportunities(self, limit=500):
        return list(self.existing_opps)

    def promote_candidate_transactional(self, candidate_id, opportunity, is_update=False, update_fields=None):
        self.promoted_records.append({
            "candidate_id": candidate_id,
            "opportunity_id": opportunity.id,
            "is_update": is_update,
            "update_fields": update_fields,
        })
        return opportunity.id

    def mark_candidate_promotion_status(self, candidate_id, status, reason=""):
        self.marked_statuses.append({
            "candidate_id": candidate_id,
            "status": status,
            "reason": reason,
        })


class TestProductionPromotionService:
    """Test suite for approval gate, deduplication, and transactional promotion."""

    def test_approved_candidate_dry_run_promotion(self):
        """Verifies approved candidate evaluates to DRY_RUN when dry_run=True with 0 writes."""
        cand = {
            "id": "cand-01",
            "title": "CERT-In Cyber Defense Internship 2026",
            "canonical_url": "https://cert-in.org.in/internship/apply",
            "source_domain": "cert-in.org.in",
            "country_or_scope": "India",
            "category": "internship",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {
                    "decision": "APPROVED",
                    "pricing_verification_status": "VERIFIED_FREE",
                    "participant_cost_status": "FREE",
                },
                "classification": {
                    "title": "CERT-In Cyber Defense Internship 2026",
                    "organization": "CERT-In",
                    "category": "internship",
                    "description": "Government cybersecurity internship for Indian students.",
                    "country_or_scope": "India",
                    "is_remote": False,
                    "deadline": "2027-06-30",
                    "application_url": "https://cert-in.org.in/internship/apply",
                }
            })
        }

        mock_repo = MockPromotionRepository(candidates=[cand])
        service = ProductionPromotionService(repository=mock_repo, dry_run=True, enabled=False)

        summary = service.promote_candidates(run_id="test-run-1", dry_run=True)
        assert summary.candidates_evaluated == 1
        assert summary.candidates_promoted == 1
        assert len(mock_repo.promoted_records) == 0, "Dry run must NOT execute DB writes"
        assert summary.evaluations[0].decision == PromotionDecision.DRY_RUN

    def test_approved_candidate_live_promotion_writes_to_repo(self):
        """Verifies approved candidate is written to repo when enabled=True and dry_run=False."""
        cand = {
            "id": "cand-02",
            "title": "National Cyber Challenge CTF 2026",
            "canonical_url": "https://ctf.example.com/2026",
            "source_domain": "ctf.example.com",
            "category": "ctf",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {
                    "title": "National Cyber Challenge CTF 2026",
                    "category": "ctf",
                    "description": "Annual free-entry national capture the flag event.",
                    "application_url": "https://ctf.example.com/2026/register",
                }
            })
        }

        mock_repo = MockPromotionRepository(candidates=[cand])
        service = ProductionPromotionService(repository=mock_repo, dry_run=False, enabled=True)

        summary = service.promote_candidates(run_id="test-run-2", dry_run=False)
        assert summary.candidates_promoted == 1
        assert len(mock_repo.promoted_records) == 1
        assert mock_repo.promoted_records[0]["candidate_id"] == "cand-02"

    def test_rejected_candidate_blocked(self):
        """Verifies candidate with free_only_decision=REJECTED is blocked from promotion."""
        cand = {
            "id": "cand-03",
            "title": "Commercial Ethical Hacking Bootcamp",
            "canonical_url": "https://bootcamp.example.com",
            "free_only_decision": "REJECTED",
            "pricing_verification_status": "VERIFIED_PAID",
            "metadata": json.dumps({"free_only_verification": {"decision": "REJECTED"}}),
        }

        mock_repo = MockPromotionRepository(candidates=[cand])
        service = ProductionPromotionService(repository=mock_repo, dry_run=False, enabled=True)

        eval_res = service.evaluate_candidate_for_promotion(cand, [])
        assert eval_res.decision == PromotionDecision.BLOCKED_REJECTED
        assert "must be APPROVED" in eval_res.reason

    def test_quarantined_candidate_blocked(self):
        """Verifies candidate with free_only_decision=QUARANTINED is blocked."""
        cand = {
            "id": "cand-04",
            "title": "Unknown Cyber Workshop",
            "canonical_url": "https://workshop.example.com",
            "free_only_decision": "QUARANTINED",
            "pricing_verification_status": "UNCERTAIN",
            "metadata": json.dumps({"free_only_verification": {"decision": "QUARANTINED"}}),
        }

        mock_repo = MockPromotionRepository(candidates=[cand])
        service = ProductionPromotionService(repository=mock_repo, dry_run=False, enabled=True)

        eval_res = service.evaluate_candidate_for_promotion(cand, [])
        assert eval_res.decision == PromotionDecision.BLOCKED_QUARANTINED

    def test_missing_required_fields_blocked(self):
        """Verifies candidate with invalid/empty fields is blocked."""
        cand = {
            "id": "cand-05",
            "title": "AB", # Too short (<3 chars)
            "canonical_url": "not-a-valid-url",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {"title": "AB", "description": "Too short"},
            }),
        }

        mock_repo = MockPromotionRepository(candidates=[cand])
        service = ProductionPromotionService(repository=mock_repo, dry_run=False, enabled=True)

        eval_res = service.evaluate_candidate_for_promotion(cand, [])
        assert eval_res.decision == PromotionDecision.BLOCKED_INVALID

    def test_expired_candidate_blocked(self):
        """Verifies opportunity with past deadline is blocked from promotion."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        cand = {
            "id": "cand-06",
            "title": "Past Bug Bounty Contest",
            "canonical_url": "https://bounty.example.com",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {
                    "title": "Past Bug Bounty Contest",
                    "description": "Contest that closed yesterday.",
                    "deadline": yesterday,
                },
            }),
        }

        mock_repo = MockPromotionRepository(candidates=[cand])
        service = ProductionPromotionService(repository=mock_repo, dry_run=False, enabled=True)

        eval_res = service.evaluate_candidate_for_promotion(cand, [])
        assert eval_res.decision == PromotionDecision.BLOCKED_INVALID
        assert "expired" in eval_res.reason

    def test_existing_opportunity_updated_when_changes_detected(self):
        """Verifies existing opportunity is updated rather than duplicated when changes detected."""
        existing_opp = Opportunity(
            id="opp-existing-99",
            title="DefCon India CTF 2026",
            url="https://defcon-india.example.com/ctf",
            canonical_url="https://defcon-india.example.com/ctf",
            source_id="tavily",
            deadline="2027-05-01",
            description="Short overview.",
        )

        cand = {
            "id": "cand-07",
            "title": "DefCon India CTF 2026",
            "canonical_url": "https://defcon-india.example.com/ctf",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {
                    "title": "DefCon India CTF 2026",
                    "deadline": "2027-05-15", # Updated deadline
                    "description": "Comprehensive multi-category CTF competition with jeopardy and attack-defense stages for security researchers.",
                },
            }),
        }

        mock_repo = MockPromotionRepository(candidates=[cand], existing_opps=[existing_opp])
        service = ProductionPromotionService(repository=mock_repo, dry_run=False, enabled=True)

        eval_res = service.evaluate_candidate_for_promotion(cand, [existing_opp])
        assert eval_res.decision == PromotionDecision.UPDATED
        assert eval_res.opportunity_id == "opp-existing-99"
        assert "deadline" in eval_res.changes_detected
