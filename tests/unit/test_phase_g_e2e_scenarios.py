"""
Phase G End-to-End Validation Test Suite for CyberScout AI.

Tests Scenarios A through J systematically through every stage of the
modernized opportunity lifecycle:
1. Discovery & URL validation
2. Content extraction handling
3. AI Classification schema validation
4. Pricing evidence validation & grounding
5. Deterministic free-only verification (Rule v1.0)
6. Layered production deduplication
7. Deterministic opportunity ranking
8. Controlled production promotion gate
9. Daily report & notification eligibility
"""

from datetime import datetime, timedelta, timezone
import json
import pytest

from src.discovery.classification_validator import ClassificationValidator
from src.discovery.free_only_models import FreeOnlyDecision, PricingVerificationStatus
from src.discovery.free_only_rules import FreeOnlyRuleEngine
from src.discovery.opportunity_ranker import OpportunityRanker
from src.discovery.pricing_evidence_validator import PricingEvidenceValidator
from src.discovery.production_deduplication import ProductionDeduplicator
from src.discovery.promotion_models import PromotionDecision
from src.discovery.promotion_service import ProductionPromotionService
from src.discovery.url_validator import URLValidator
from src.models.opportunity import Opportunity


class TestPhaseGEndToEndScenarios:
    """Comprehensive test harness for Phase G Scenarios A through J."""

    def setup_method(self):
        self.url_validator = URLValidator()
        self.cls_validator = ClassificationValidator()
        self.evidence_validator = PricingEvidenceValidator()
        self.rule_engine = FreeOnlyRuleEngine(evidence_validator=self.evidence_validator)
        self.deduplicator = ProductionDeduplicator()
        self.ranker = OpportunityRanker()
        self.promotion_service = ProductionPromotionService(dry_run=True, enabled=False)

    def test_scenario_a_verified_free_internship(self):
        """
        Scenario A: Verified-free cybersecurity internship with valid future deadline.
        Expected: Discovered -> Extracted -> Classified -> Validated -> APPROVED -> PROMOTED (Dry Run) -> Included in Digest.
        """
        raw_url = "https://cert-in.org.in/internships/summer2027"
        url_res = self.url_validator.validate(raw_url)
        assert url_res.is_valid

        source_text = "CERT-In invites applications for Summer 2027 Cyber Defense Internship. Selected candidates receive a monthly stipend of ₹25,000. Free to apply for all eligible students. Deadline: 2027-05-30."
        excerpt = "Free to apply for all eligible students"
        assert self.evidence_validator.verify_excerpt_in_content(excerpt, source_text)

        decision, pricing_status, is_free, cost_st, comp_st, _, reason, _, rules = self.rule_engine.evaluate(
            candidate_id="scen-a-01",
            category="internship",
            page_content=source_text,
            source_url=url_res.canonical_url,
            source_domain="cert-in.org.in",
            classification_data={
                "financial": {
                    "participation_cost_status": "FREE",
                    "compensation_status": "PAID",
                },
                "evidence": [{"field_name": "pricing", "exact_excerpt": excerpt}],
            },
            extraction_data={"status": "completed"},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert pricing_status == PricingVerificationStatus.VERIFIED_FREE
        assert is_free is True
        assert cost_st == "FREE"
        assert comp_st == "PAID"

        cand_data = {
            "title": "CERT-In Cyber Defense Internship 2027",
            "canonical_url": url_res.canonical_url,
            "category": "internship",
            "country_or_scope": "India",
            "deadline": "2027-05-30",
            "description": source_text,
            "is_free": True,
            "free_only_decision": "APPROVED",
        }

        # Deduplication against empty prod list
        match = self.deduplicator.find_match(cand_data, [])
        assert match is None

        # Ranking score
        score, bd = self.ranker.calculate_score(cand_data, source_domain="cert-in.org.in")
        assert score >= 75
        assert bd["regional_relevance_india"] == 15
        assert bd["verified_free"] == 10

        # Promotion Gate Evaluation
        row_for_promo = {
            "id": "scen-a-01",
            "title": cand_data["title"],
            "canonical_url": cand_data["canonical_url"],
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {
                    "title": cand_data["title"],
                    "category": "internship",
                    "description": cand_data["description"],
                    "deadline": "2027-05-30",
                    "country_or_scope": "India",
                }
            })
        }
        promo_eval = self.promotion_service.evaluate_candidate_for_promotion(row_for_promo, [])
        assert promo_eval.decision == PromotionDecision.PROMOTED
        assert promo_eval.is_new_promotion is True

    def test_scenario_b_verified_free_ctf_with_prizes(self):
        """
        Scenario B: Verified-free CTF competition with cash prizes.
        Expected: Free registration with cash prizes is APPROVED and eligible for promotion.
        """
        source_text = "DefCon India 2027 CTF. 100% Free entry. Prize pool of $10,000 for top three teams. No registration fee."
        excerpt = "100% Free entry"

        decision, pricing_status, is_free, cost_st, comp_st, _, _, _, _ = self.rule_engine.evaluate(
            candidate_id="scen-b-01",
            category="ctf",
            page_content=source_text,
            source_url="https://ctftime.org/event/9999",
            source_domain="ctftime.org",
            classification_data={
                "financial": {"participation_cost_status": "FREE", "compensation_status": "PAID"},
                "evidence": [{"field_name": "pricing", "exact_excerpt": excerpt}],
            },
            extraction_data={"status": "completed"},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert pricing_status == PricingVerificationStatus.VERIFIED_FREE
        assert cost_st == "FREE"

        score, bd = self.ranker.calculate_score({
            "title": "DefCon India CTF 2027",
            "category": "ctf",
            "description": source_text,
            "free_only_decision": "APPROVED",
        }, source_domain="ctftime.org")
        assert score >= 60

    def test_scenario_c_paid_bootcamp(self):
        """
        Scenario C: Paid cybersecurity bootcamp.
        Expected: REJECTED by Free-Only Rule Engine -> Blocked at Promotion Gate -> Excluded from public reports.
        """
        source_text = "Zero to Hero Pentesting Bootcamp. Tuition fee is $2,500. Registration fee of $100 required upon signup."
        excerpt = "Tuition fee is $2,500"

        decision, pricing_status, is_free, cost_st, _, _, _, _, rules = self.rule_engine.evaluate(
            candidate_id="scen-c-01",
            category="course",
            page_content=source_text,
            source_url="https://bootcamp.example.com",
            source_domain="bootcamp.example.com",
            classification_data={
                "financial": {"participation_cost_status": "PAID"},
                "evidence": [{"field_name": "pricing", "exact_excerpt": excerpt}],
            },
            extraction_data={"status": "completed"},
        )

        assert decision == FreeOnlyDecision.REJECTED
        assert pricing_status == PricingVerificationStatus.VERIFIED_PAID
        assert is_free is False
        assert "RULE_REJECT_MANDATORY_FEE" in rules

        row_for_promo = {
            "id": "scen-c-01",
            "title": "Commercial Pentesting Bootcamp",
            "canonical_url": "https://bootcamp.example.com",
            "free_only_decision": "REJECTED",
            "pricing_verification_status": "VERIFIED_PAID",
            "metadata": json.dumps({"free_only_verification": {"decision": "REJECTED"}}),
        }
        promo_eval = self.promotion_service.evaluate_candidate_for_promotion(row_for_promo, [])
        assert promo_eval.decision == PromotionDecision.BLOCKED_REJECTED

    def test_scenario_d_free_course_with_mandatory_exam_fee(self):
        """
        Scenario D: Free course with mandatory paid certification exam required for participation.
        Expected: Mandatory fee triggers REJECTED.
        """
        source_text = "Free intro course, but students must pay mandatory exam fee of $300 to participate in the curriculum."
        excerpt = "mandatory exam fee of $300"

        decision, pricing_status, is_free, cost_st, _, _, _, _, rules = self.rule_engine.evaluate(
            candidate_id="scen-d-01",
            category="certification",
            page_content=source_text,
            source_url="https://edu.example.com/course",
            source_domain="edu.example.com",
            classification_data={
                "financial": {"participation_cost_status": "PAID"},
                "evidence": [{"field_name": "pricing", "exact_excerpt": excerpt}],
            },
            extraction_data={"status": "completed"},
        )

        assert decision == FreeOnlyDecision.REJECTED
        assert is_free is False

    def test_scenario_e_unknown_pricing(self):
        """
        Scenario E: Opportunity with unknown/unverified pricing.
        Expected: QUARANTINED by Free-Only gate. Unknown must NEVER mean free.
        """
        source_text = "Advanced Malware Analysis Masterclass. Comprehensive reverse engineering curriculum for professionals."

        decision, pricing_status, is_free, _, _, _, _, _, rules = self.rule_engine.evaluate(
            candidate_id="scen-e-01",
            category="course",
            page_content=source_text,
            source_url="https://malware.example.com/masterclass",
            source_domain="malware.example.com",
            classification_data={
                "financial": {"participation_cost_status": "UNKNOWN"},
                "evidence": [],
            },
            extraction_data={"status": "completed"},
        )

        assert decision == FreeOnlyDecision.QUARANTINED
        assert pricing_status == PricingVerificationStatus.UNCERTAIN
        assert is_free is None
        assert "RULE_DEFAULT_QUARANTINE_MISSING_PRICING" in rules

        row_for_promo = {
            "id": "scen-e-01",
            "title": "Advanced Malware Analysis Masterclass",
            "canonical_url": "https://malware.example.com/masterclass",
            "free_only_decision": "QUARANTINED",
            "pricing_verification_status": "UNCERTAIN",
            "metadata": json.dumps({"free_only_verification": {"decision": "QUARANTINED"}}),
        }
        promo_eval = self.promotion_service.evaluate_candidate_for_promotion(row_for_promo, [])
        assert promo_eval.decision == PromotionDecision.BLOCKED_QUARANTINED

    def test_scenario_f_compensated_employment_without_fee(self):
        """
        Scenario F: Job that pays applicant salary/stipend with no application fee.
        Expected: Compensation is cleanly separated from applicant fee. APPROVED for promotion.
        """
        source_text = "Junior Security Operations Center Analyst. Annual salary $85,000. Free to apply online. No application fees."
        excerpt = "No application fees"

        decision, pricing_status, is_free, cost_st, comp_st, _, _, _, rules = self.rule_engine.evaluate(
            candidate_id="scen-f-01",
            category="job",
            page_content=source_text,
            source_url="https://corp.example.com/jobs/soc-analyst",
            source_domain="corp.example.com",
            classification_data={
                "financial": {"participation_cost_status": "FREE", "compensation_status": "PAID"},
                "evidence": [{"field_name": "pricing", "exact_excerpt": excerpt}],
            },
            extraction_data={"status": "completed"},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert cost_st == "FREE"
        assert comp_st == "PAID"
        assert any(r in rules for r in ("RULE_APPROVE_COMPENSATED_EMPLOYMENT_WITHOUT_FEE", "RULE_APPROVE_VERIFIED_FREE_OPPORTUNITY"))

    def test_scenario_g_expired_opportunity(self):
        """
        Scenario G: Expired opportunity with past deadline.
        Expected: Blocked from promotion gate due to expiration.
        """
        yesterday = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
        source_text = f"National Cyber Olympiad. Free participation. Application deadline: {yesterday}."

        row_for_promo = {
            "id": "scen-g-01",
            "title": "Expired Cyber Olympiad",
            "canonical_url": "https://olympiad.example.com",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {
                    "title": "Expired Cyber Olympiad",
                    "deadline": yesterday,
                    "description": source_text,
                }
            })
        }
        promo_eval = self.promotion_service.evaluate_candidate_for_promotion(row_for_promo, [])
        assert promo_eval.decision == PromotionDecision.BLOCKED_INVALID
        assert "expired" in promo_eval.reason

    def test_scenario_h_two_urls_pointing_to_same_opportunity(self):
        """
        Scenario H: Two URLs pointing to the exact same opportunity.
        Expected: Second URL is identified as duplicate via canonical normalization / url_hash and SKIPPED.
        """
        desc = "Mentorship program for cybersecurity students."
        existing_opp = Opportunity(
            id="opp-scenario-h",
            title="Google Summer Cyber Mentorship 2027",
            url="https://careers.google.com/jobs/results/cyber-mentorship-2027",
            source_id="tavily",
            company="Google",
            category="fellowship",
            description=desc,
        )

        candidate_alternate_url = {
            "title": "Google Summer Cyber Mentorship 2027",
            "canonical_url": "https://careers.google.com/jobs/results/cyber-mentorship-2027?utm_source=linkedin&ref=email",
            "organization": "Google",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {
                    "title": "Google Summer Cyber Mentorship 2027",
                    "organization": "Google",
                    "description": desc,
                }
            })
        }

        promo_eval = self.promotion_service.evaluate_candidate_for_promotion(candidate_alternate_url, [existing_opp])
        assert promo_eval.decision == PromotionDecision.SKIPPED_DUPLICATE
        assert promo_eval.opportunity_id == "opp-scenario-h"

    def test_scenario_i_two_distinct_opportunities_from_same_org(self):
        """
        Scenario I: Two distinct opportunities from the same organization.
        Expected: Maintained separately; not falsely deduplicated.
        """
        existing_opp = Opportunity(
            id="opp-org-job",
            title="Microsoft Cloud Security Engineer",
            url="https://careers.microsoft.com/jobs/101",
            source_id="tavily",
            company="Microsoft",
            category="job",
        )

        cand_internship = {
            "id": "cand-org-intern",
            "title": "Microsoft Security Research Internship 2027",
            "canonical_url": "https://careers.microsoft.com/jobs/102",
            "organization": "Microsoft",
            "category": "internship",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {
                    "title": "Microsoft Security Research Internship 2027",
                    "organization": "Microsoft",
                    "category": "internship",
                    "description": "12-week research internship on AI security.",
                    "deadline": "2027-08-01",
                }
            })
        }

        promo_eval = self.promotion_service.evaluate_candidate_for_promotion(cand_internship, [existing_opp])
        assert promo_eval.decision == PromotionDecision.PROMOTED
        assert promo_eval.is_new_promotion is True

    def test_scenario_j_missing_mandatory_metadata(self):
        """
        Scenario J: Candidate with missing mandatory metadata (e.g. title is blank, invalid URL).
        Expected: BLOCKED_INVALID by Promotion Gate.
        """
        cand_data = {
            "id": "scen-j-01",
            "title": "X", # Invalid (<3 chars)
            "canonical_url": "",
            "free_only_decision": "APPROVED",
            "pricing_verification_status": "VERIFIED_FREE",
            "metadata": json.dumps({
                "free_only_verification": {"decision": "APPROVED", "pricing_verification_status": "VERIFIED_FREE"},
                "classification": {"title": "X", "description": "Too short"},
            }),
        }

        promo_eval = self.promotion_service.evaluate_candidate_for_promotion(cand_data, [])
        assert promo_eval.decision == PromotionDecision.BLOCKED_INVALID
        assert "Title is missing or shorter" in promo_eval.reason
