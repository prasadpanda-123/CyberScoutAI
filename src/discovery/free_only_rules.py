"""
Deterministic Free-Only Business Rules (Phase E).

Encapsulates explicit, reproducible Python business rules governing the
three-state decision (APPROVED, REJECTED, QUARANTINED) without LLM calls.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.core.logging import get_logger
from src.discovery.free_only_models import (
    FinancialDimension,
    FreeOnlyDecision,
    PricingVerificationStatus,
    VerifiedPricingEvidence,
)
from src.discovery.pricing_evidence_validator import PricingEvidenceValidator

logger = get_logger(__name__)

FREE_ONLY_RULE_VERSION = "v1.0"


class FreeOnlyRuleEngine:
    """
    Deterministic rule engine evaluating extracted opportunity evidence to decide
    eligibility under the CyberScout AI free-only policy.
    """

    def __init__(self, evidence_validator: Optional[PricingEvidenceValidator] = None):
        self.validator = evidence_validator or PricingEvidenceValidator()
        self.version = FREE_ONLY_RULE_VERSION

    def evaluate(
        self,
        candidate_id: str,
        category: str,
        page_content: str,
        source_url: str,
        source_domain: str,
        classification_data: Dict[str, Any],
        extraction_data: Dict[str, Any],
    ) -> Tuple[FreeOnlyDecision, PricingVerificationStatus, Optional[bool], str, str, str, str, List[VerifiedPricingEvidence], List[str]]:
        """
        Executes deterministic rules in strict order of precedence.

        Returns:
            Tuple of:
            - decision (FreeOnlyDecision): APPROVED, REJECTED, or QUARANTINED
            - pricing_status (PricingVerificationStatus): VERIFIED_FREE, VERIFIED_PAID, UNCERTAIN
            - is_free (Optional[bool]): True, False, or None
            - participant_cost_status (str): 'FREE', 'PAID', 'UNCERTAIN'
            - participant_compensation_status (str): 'PAID', 'UNPAID', 'UNKNOWN'
            - mandatory_fee_status (str): 'FREE', 'PAID', 'UNKNOWN'
            - verification_reason (str): Human-readable decision explanation
            - verified_evidence (List[VerifiedPricingEvidence]): Verified evidence items
            - rules_triggered (List[str]): Audit list of triggered rule IDs
        """
        rules_triggered: List[str] = []
        verified_evidence: List[VerifiedPricingEvidence] = []

        # 1. Inspect Content & Scrape Status
        if not page_content or len(page_content.strip()) < 30:
            return (
                FreeOnlyDecision.QUARANTINED,
                PricingVerificationStatus.UNCERTAIN,
                None,
                "UNCERTAIN",
                "UNKNOWN",
                "UNKNOWN",
                "Quarantined: Extracted source content is missing, inaccessible, or below minimum length.",
                [],
                ["RULE_QUARANTINE_INSUFFICIENT_SOURCE"],
            )

        # 2. Extract Phase D Financial Metadata & Evidence
        fin_meta = classification_data.get("financial") or {}
        raw_evidence_list = classification_data.get("evidence") or []
        ai_cost_status = fin_meta.get("participation_cost_status", "UNCERTAIN").upper()
        ai_app_fee = fin_meta.get("application_fee_status", "UNKNOWN").upper()
        ai_reg_fee = fin_meta.get("registration_fee_status", "UNKNOWN").upper()
        ai_comp_status = fin_meta.get("compensation_status", "UNKNOWN").upper()
        ai_comp_details = fin_meta.get("compensation_details") or ""

        # 3. Independent Regex Scans across Raw Page Content
        content_mandatory_fees = self.validator.scan_for_mandatory_fees(page_content)
        content_free_evidence = self.validator.scan_for_free_evidence(page_content)
        content_compensation = self.validator.scan_for_compensation(page_content)
        is_trusted_domain = self.validator.is_trusted_official_domain(source_domain)

        # 4. Validate Phase D Evidence Excerpts Against Source Text
        unverified_excerpts = False
        for ev in raw_evidence_list:
            if isinstance(ev, dict):
                excerpt = ev.get("exact_excerpt", "")
                field_name = ev.get("field_name", "")
                if excerpt:
                    exists = self.validator.verify_excerpt_in_content(excerpt, page_content)
                    if exists:
                        dim = FinancialDimension.GENERAL_PARTICIPATION.value
                        if "fee" in field_name.lower():
                            dim = FinancialDimension.APPLICATION_FEE.value
                        elif "comp" in field_name.lower():
                            dim = FinancialDimension.PARTICIPANT_COMPENSATION.value
                        verified_evidence.append(
                            VerifiedPricingEvidence(
                                source_url=source_url,
                                original_pricing_statement=excerpt,
                                supporting_excerpt=excerpt,
                                financial_dimension=dim,
                                is_verified_in_source=True,
                            )
                        )
                    else:
                        unverified_excerpts = True
                        logger.debug(f"[FreeOnlyRules] Cited excerpt not found in source text: '{excerpt[:40]}...'")

        # 5. Populate verified evidence from direct content scans if available
        for stmt, amt, dim in content_mandatory_fees:
            verified_evidence.append(
                VerifiedPricingEvidence(
                    source_url=source_url,
                    original_pricing_statement=stmt,
                    supporting_excerpt=stmt,
                    financial_dimension=dim.value,
                    is_verified_in_source=True,
                )
            )

        for free_stmt in content_free_evidence[:2]:
            verified_evidence.append(
                VerifiedPricingEvidence(
                    source_url=source_url,
                    original_pricing_statement=free_stmt,
                    supporting_excerpt=free_stmt,
                    financial_dimension=FinancialDimension.GENERAL_PARTICIPATION.value,
                    is_verified_in_source=True,
                )
            )

        # ---------------------------------------------------------
        # PRECEDENCE RULE 1: MANDATORY PARTICIPANT FEES -> REJECTED
        # ---------------------------------------------------------
        # If explicit mandatory fee found in content or AI confirmed with evidence
        has_mandatory_fee = len(content_mandatory_fees) > 0 or ai_cost_status == "PAID" or ai_app_fee == "PAID" or ai_reg_fee == "PAID"
        has_affirmative_free = len(content_free_evidence) > 0 or ai_cost_status == "FREE"

        if has_mandatory_fee and not has_affirmative_free:
            reasons = []
            if content_mandatory_fees:
                reasons.append(f"mandatory {content_mandatory_fees[0][2].value} identified ({content_mandatory_fees[0][0][:60]})")
            elif ai_app_fee == "PAID":
                reasons.append("application fee required")
            elif ai_reg_fee == "PAID":
                reasons.append("registration fee required")
            else:
                reasons.append("participation fee required")

            rules_triggered.append("RULE_REJECT_MANDATORY_FEE")
            return (
                FreeOnlyDecision.REJECTED,
                PricingVerificationStatus.VERIFIED_PAID,
                False,
                "PAID",
                ai_comp_status,
                "PAID",
                f"Rejected: Opportunity violates free-only policy due to {', '.join(reasons)}.",
                verified_evidence,
                rules_triggered,
            )

        # ---------------------------------------------------------
        # PRECEDENCE RULE 2: CONTRADICTORY PRICING -> QUARANTINED
        # ---------------------------------------------------------
        # Both affirmative free claim AND mandatory fee claim present
        if has_mandatory_fee and has_affirmative_free:
            rules_triggered.append("RULE_QUARANTINE_CONTRADICTORY_PRICING")
            return (
                FreeOnlyDecision.QUARANTINED,
                PricingVerificationStatus.UNCERTAIN,
                None,
                "UNCERTAIN",
                ai_comp_status,
                "UNKNOWN",
                "Quarantined: Conflicting pricing evidence detected (source mentions both free admission and a mandatory fee).",
                verified_evidence,
                rules_triggered,
            )

        # ---------------------------------------------------------
        # PRECEDENCE RULE 3: UNVERIFIED / HALLUCINATED EXCERPTS -> QUARANTINED
        # ---------------------------------------------------------
        if unverified_excerpts and not content_free_evidence and not is_trusted_domain:
            rules_triggered.append("RULE_QUARANTINE_UNVERIFIED_EVIDENCE")
            return (
                FreeOnlyDecision.QUARANTINED,
                PricingVerificationStatus.UNCERTAIN,
                None,
                "UNCERTAIN",
                ai_comp_status,
                "UNKNOWN",
                "Quarantined: Cited pricing evidence excerpt could not be verified in the extracted source text.",
                verified_evidence,
                rules_triggered,
            )

        # ---------------------------------------------------------
        # PRECEDENCE RULE 4: VERIFIED FREE OPPORTUNITY -> APPROVED
        # ---------------------------------------------------------
        if content_free_evidence or (ai_cost_status == "FREE" and len(verified_evidence) > 0):
            rules_triggered.append("RULE_APPROVE_VERIFIED_FREE_OPPORTUNITY")
            comp_status = "PAID" if (content_compensation or ai_comp_status == "PAID") else "UNKNOWN"
            return (
                FreeOnlyDecision.APPROVED,
                PricingVerificationStatus.VERIFIED_FREE,
                True,
                "FREE",
                comp_status,
                "FREE",
                "Approved: Verified affirmative free participation with zero mandatory fees.",
                verified_evidence,
                rules_triggered,
            )

        # ---------------------------------------------------------
        # PRECEDENCE RULE 5: COMPENSATED JOBS / INTERNSHIPS -> APPROVED
        # ---------------------------------------------------------
        # Standard employment: If job/internship pays a salary/stipend and has no application fee
        clean_cat = category.strip().lower()
        if clean_cat in ("job", "internship", "research_opportunity"):
            has_compensation = bool(content_compensation or ai_comp_status == "PAID" or ai_comp_details)
            if has_compensation and not has_mandatory_fee:
                rules_triggered.append("RULE_APPROVE_COMPENSATED_EMPLOYMENT_WITHOUT_FEE")
                return (
                    FreeOnlyDecision.APPROVED,
                    PricingVerificationStatus.VERIFIED_FREE,
                    True,
                    "FREE",
                    "PAID",
                    "FREE",
                    "Approved: Paid employment/internship opportunity with compensation and no application fee.",
                    verified_evidence,
                    rules_triggered,
                )

        # ---------------------------------------------------------
        # PRECEDENCE RULE 6: TRUSTED COMPETITIONS & BUG BOUNTIES -> APPROVED
        # ---------------------------------------------------------
        # CTFs, Bug Bounties, VDPs on trusted platforms (CTFtime, HackerOne, Bugcrowd, Unstop)
        if clean_cat in ("ctf", "bug_bounty", "vulnerability_disclosure", "hackathon"):
            if is_trusted_domain and not has_mandatory_fee:
                rules_triggered.append("RULE_APPROVE_TRUSTED_FREE_COMPETITION")
                comp_status = "PAID" if (content_compensation or ai_comp_status == "PAID") else "UNKNOWN"
                return (
                    FreeOnlyDecision.APPROVED,
                    PricingVerificationStatus.VERIFIED_FREE,
                    True,
                    "FREE",
                    comp_status,
                    "FREE",
                    f"Approved: Official cybersecurity competition/program on verified platform '{source_domain}' with zero entry fees.",
                    verified_evidence,
                    rules_triggered,
                )

        # ---------------------------------------------------------
        # PRECEDENCE RULE 7: DEFAULT SAFE QUARANTINE
        # ---------------------------------------------------------
        # Unknown never means free!
        rules_triggered.append("RULE_DEFAULT_QUARANTINE_MISSING_PRICING")
        return (
            FreeOnlyDecision.QUARANTINED,
            PricingVerificationStatus.UNCERTAIN,
            None,
            "UNCERTAIN",
            ai_comp_status,
            "UNKNOWN",
            "Quarantined: Pricing is not explicitly stated or confirmed in source page evidence.",
            verified_evidence,
            rules_triggered,
        )

