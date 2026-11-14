"""
Domain Models and Enums for Deterministic Free-Only Verification (Phase E).

Defines the authoritative decision types, financial dimension enums, evidence models,
and evaluation summaries used by the Python-based free-only verification engine.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class FreeOnlyDecision(str, Enum):
    """
    Authoritative three-state decision for candidate eligibility.
    Unknown must never mean free.
    """

    APPROVED = "APPROVED"       # Verified free to apply for or participate in
    REJECTED = "REJECTED"       # Requires mandatory payment violating free-only policy
    QUARANTINED = "QUARANTINED" # Pricing missing, ambiguous, contradictory, or ungrounded


class PricingVerificationStatus(str, Enum):
    """Economic status classification."""

    VERIFIED_FREE = "VERIFIED_FREE"
    VERIFIED_PAID = "VERIFIED_PAID"
    UNCERTAIN = "UNCERTAIN"


class FinancialDimension(str, Enum):
    """Individual financial dimensions evaluated by the deterministic rule engine."""

    APPLICATION_FEE = "application_fee"
    REGISTRATION_FEE = "registration_fee"
    TUITION_OR_COURSE_FEE = "tuition_or_course_fee"
    MANDATORY_EXAMINATION = "mandatory_examination"
    MANDATORY_CERTIFICATION = "mandatory_certification"
    MANDATORY_MEMBERSHIP = "mandatory_membership"
    MANDATORY_PURCHASE = "mandatory_purchase"
    PARTICIPANT_COMPENSATION = "participant_compensation"
    GENERAL_PARTICIPATION = "general_participation"


@dataclass
class VerifiedPricingEvidence:
    """Evidence item linking a pricing claim to source page content."""

    source_url: str
    original_pricing_statement: str
    supporting_excerpt: str
    financial_dimension: str
    is_verified_in_source: bool
    evidence_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    section_identifier: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FreeOnlyEvaluation:
    """
    Deterministic evaluation output produced by Python business rules.
    Operates independently of LLM/AI output.
    """

    candidate_id: str
    decision: FreeOnlyDecision
    pricing_verification_status: PricingVerificationStatus
    is_free: Optional[bool]  # True if APPROVED, False if REJECTED, None if QUARANTINED
    participant_cost_status: str  # 'FREE', 'PAID', 'UNCERTAIN'
    participant_compensation_status: str  # 'PAID', 'UNPAID', 'UNKNOWN'
    mandatory_fee_status: str  # 'FREE', 'PAID', 'UNKNOWN'
    verified_evidence: List[VerifiedPricingEvidence] = field(default_factory=list)
    verification_reason: str = ""
    rule_version: str = "v1.0"
    rules_triggered: List[str] = field(default_factory=list)
    verified_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision.value,
            "pricing_verification_status": self.pricing_verification_status.value,
            "is_free": self.is_free,
            "participant_cost_status": self.participant_cost_status,
            "participant_compensation_status": self.participant_compensation_status,
            "mandatory_fee_status": self.mandatory_fee_status,
            "verified_evidence": [e.to_dict() for e in self.verified_evidence],
            "verification_reason": self.verification_reason,
            "rule_version": self.rule_version,
            "rules_triggered": self.rules_triggered,
            "verified_at": self.verified_at,
        }


@dataclass
class FreeOnlyRunSummary:
    """Summary metrics and audit record for an executed Free-Only verification run."""

    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    candidates_evaluated: int = 0
    candidates_approved: int = 0
    candidates_rejected: int = 0
    candidates_quarantined: int = 0
    rejection_reasons_breakdown: Dict[str, int] = field(default_factory=dict)
    quarantine_reasons_breakdown: Dict[str, int] = field(default_factory=dict)
    status: str = "completed"
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

