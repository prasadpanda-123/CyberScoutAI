"""
Promotion Models and Data Transfer Objects for CyberScout AI.

Defines types, enums, evaluation structures, and run summaries for the
Phase F Controlled Production Promotion, Deduplication, Ranking & Notification engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class PromotionDecision(str, Enum):
    """Authoritative decision outcome for candidate promotion into Opportunities."""
    PROMOTED = "PROMOTED"                 # Genuinely new opportunity promoted into production table
    UPDATED = "UPDATED"                   # Existing production opportunity updated with enriched data
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE" # Matches existing production opportunity with no changes
    BLOCKED_REJECTED = "BLOCKED_REJECTED" # Candidate rejected by deterministic Free-Only gate
    BLOCKED_QUARANTINED = "BLOCKED_QUARANTINED" # Candidate quarantined by Free-Only gate
    BLOCKED_INVALID = "BLOCKED_INVALID"   # Candidate failed schema/field validation or expired
    DRY_RUN = "DRY_RUN"                   # Evaluation succeeded under dry-run (no DB writes)


class PromotionStatus(str, Enum):
    """Database processing status stored on DiscoveredCandidates records."""
    UNPROMOTED = "unpromoted"
    PROMOTED = "promoted"
    UPDATED = "updated"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class OpportunityFieldValidationResult:
    """Result of schema and field validation on candidate before promotion."""
    is_valid: bool
    missing_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "missing_fields": self.missing_fields,
            "errors": self.errors,
        }


@dataclass
class CandidatePromotionEvaluation:
    """Detailed evaluation record for a single staged candidate promotion attempt."""
    candidate_id: str
    title: str
    canonical_url: str
    decision: PromotionDecision
    opportunity_id: Optional[str] = None
    is_new_promotion: bool = False
    is_update: bool = False
    reason: str = ""
    rank_score: int = 0
    rank_breakdown: Dict[str, Any] = field(default_factory=dict)
    changes_detected: List[str] = field(default_factory=list)
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "canonical_url": self.canonical_url,
            "decision": self.decision.value,
            "opportunity_id": self.opportunity_id,
            "is_new_promotion": self.is_new_promotion,
            "is_update": self.is_update,
            "reason": self.reason,
            "rank_score": self.rank_score,
            "rank_breakdown": self.rank_breakdown,
            "changes_detected": self.changes_detected,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class PromotionRunSummary:
    """Aggregated execution summary for a production promotion run."""
    run_id: str
    candidates_evaluated: int = 0
    candidates_promoted: int = 0
    existing_updated: int = 0
    duplicates_skipped: int = 0
    blocked_unapproved: int = 0
    blocked_invalid: int = 0
    errors_count: int = 0
    promoted_opportunity_ids: List[str] = field(default_factory=list)
    updated_opportunity_ids: List[str] = field(default_factory=list)
    evaluations: List[CandidatePromotionEvaluation] = field(default_factory=list)
    dry_run: bool = True
    duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "candidates_evaluated": self.candidates_evaluated,
            "candidates_promoted": self.candidates_promoted,
            "existing_updated": self.existing_updated,
            "duplicates_skipped": self.duplicates_skipped,
            "blocked_unapproved": self.blocked_unapproved,
            "blocked_invalid": self.blocked_invalid,
            "errors_count": self.errors_count,
            "promoted_opportunity_ids": self.promoted_opportunity_ids,
            "updated_opportunity_ids": self.updated_opportunity_ids,
            "dry_run": self.dry_run,
            "duration_sec": self.duration_sec,
        }


@dataclass
class DailyReportMetadata:
    """Metrics compiled for generating the daily Excel report workbook."""
    report_date: str
    timezone: str = "Asia/Kolkata"
    total_discovered: int = 0
    total_extracted: int = 0
    total_classified: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    total_quarantined: int = 0
    newly_promoted_count: int = 0
    existing_updated_count: int = 0
    total_active_production: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_date": self.report_date,
            "timezone": self.timezone,
            "total_discovered": self.total_discovered,
            "total_extracted": self.total_extracted,
            "total_classified": self.total_classified,
            "total_approved": self.total_approved,
            "total_rejected": self.total_rejected,
            "total_quarantined": self.total_quarantined,
            "newly_promoted_count": self.newly_promoted_count,
            "existing_updated_count": self.existing_updated_count,
            "total_active_production": self.total_active_production,
        }


@dataclass
class EmailDeliveryRecord:
    """Persistent delivery tracking record ensuring daily notification idempotency."""
    report_date: str
    recipient: str
    report_identifier: str
    opportunity_ids: List[str] = field(default_factory=list)
    attachment_path: Optional[str] = None
    attachment_checksum: Optional[str] = None
    delivery_status: str = "pending" # pending, sent, failed, skipped
    attempt_count: int = 0
    max_attempts: int = 3
    provider_message_id: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    delivered_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_date": self.report_date,
            "recipient": self.recipient,
            "report_identifier": self.report_identifier,
            "opportunity_ids": self.opportunity_ids,
            "attachment_path": self.attachment_path,
            "attachment_checksum": self.attachment_checksum,
            "delivery_status": self.delivery_status,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "provider_message_id": self.provider_message_id,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
        }

