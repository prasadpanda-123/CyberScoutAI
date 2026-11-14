"""
Free-Only Verification Orchestrator for CyberScout AI (Phase E).

Executes deterministic Python business rules across candidates that completed
AI classification (Phase D), deciding whether each opportunity is APPROVED,
REJECTED, or QUARANTINED under the free-only policy.
"""

from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.discovery_models import DiscoveredCandidate
from src.discovery.free_only_models import (
    FreeOnlyDecision,
    FreeOnlyEvaluation,
    FreeOnlyRunSummary,
    PricingVerificationStatus,
)
from src.discovery.free_only_repository import FreeOnlyRepository
from src.discovery.free_only_rules import FREE_ONLY_RULE_VERSION, FreeOnlyRuleEngine
from src.discovery.pricing_evidence_validator import PricingEvidenceValidator

logger = get_logger(__name__)


class FreeOnlyVerifier:
    """
    Master service executing deterministic free-only verification without LLM calls.
    """

    def __init__(
        self,
        rule_engine: Optional[FreeOnlyRuleEngine] = None,
        repository: Optional[FreeOnlyRepository] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.rule_engine = rule_engine or FreeOnlyRuleEngine()
        self.repository = repository or FreeOnlyRepository(db_manager=self.db_manager)
        self.rule_version = FREE_ONLY_RULE_VERSION

    def run_verification(
        self,
        candidates: Optional[List[DiscoveredCandidate]] = None,
        max_candidates: int = 50,
        run_id: Optional[str] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> FreeOnlyRunSummary:
        """
        Executes free-only verification across candidates awaiting financial decision.

        Workflow:
        1. Retrieves classified candidates from DiscoveredCandidates
        2. Applies deterministic Python business rules against raw source content & evidence
        3. Issues exactly one decision: APPROVED, REJECTED, or QUARANTINED
        4. Persists evaluation in DiscoveredCandidates staging table
        5. Does NOT promote to production Opportunities table (Phase F gate)
        6. Returns FreeOnlyRunSummary
        """
        start_time = time.time()
        active_run_id = run_id or f"verify-{uuid.uuid4()}"
        started_iso = datetime.now(timezone.utc).isoformat()

        logger.info("================================================================")
        logger.info(f"[FreeOnlyVerifier] Starting Free-Only Verification Run: {active_run_id}")
        logger.info("================================================================")

        summary = FreeOnlyRunSummary(
            run_id=active_run_id,
            started_at=started_iso,
        )

        def _notify(pct: float, msg: str):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        # 1. Select Candidates
        if candidates is not None:
            target_candidates = candidates[:max_candidates]
        else:
            target_candidates = self.repository.get_candidates_for_verification(limit=max_candidates)

        summary.candidates_evaluated = len(target_candidates)
        logger.info(f"[FreeOnlyVerifier] Selected {len(target_candidates)} candidates for Free-Only verification.")

        if not target_candidates:
            summary.status = "completed"
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        total = len(target_candidates)

        for idx, candidate in enumerate(target_candidates):
            step_pct = 10.0 + ((idx / total) * 80.0)
            _notify(step_pct, f"Verifying ({idx + 1}/{total}): {candidate.title[:40]}")

            # Retrieve content and metadata
            extraction_meta = candidate.metadata.get("extraction") or {}
            classification_meta = candidate.metadata.get("classification") or {}

            page_content = (
                extraction_meta.get("main_content_markdown")
                or extraction_meta.get("main_content_html")
                or candidate.snippet
                or candidate.title
            )

            try:
                (
                    decision,
                    pricing_status,
                    is_free,
                    cost_status,
                    comp_status,
                    fee_status,
                    reason,
                    verified_ev,
                    rules_trig,
                ) = self.rule_engine.evaluate(
                    candidate_id=candidate.id,
                    category=candidate.category,
                    page_content=page_content,
                    source_url=candidate.canonical_url or candidate.original_url,
                    source_domain=candidate.source_domain,
                    classification_data=classification_meta,
                    extraction_data=extraction_meta,
                )

                evaluation = FreeOnlyEvaluation(
                    candidate_id=candidate.id,
                    decision=decision,
                    pricing_verification_status=pricing_status,
                    is_free=is_free,
                    participant_cost_status=cost_status,
                    participant_compensation_status=comp_status,
                    mandatory_fee_status=fee_status,
                    verified_evidence=verified_ev,
                    verification_reason=reason,
                    rule_version=self.rule_version,
                    rules_triggered=rules_trig,
                )

                # Track decision counts
                if decision == FreeOnlyDecision.APPROVED:
                    summary.candidates_approved += 1
                elif decision == FreeOnlyDecision.REJECTED:
                    summary.candidates_rejected += 1
                    reason_key = rules_trig[0] if rules_trig else "RULE_REJECTED"
                    summary.rejection_reasons_breakdown[reason_key] = summary.rejection_reasons_breakdown.get(reason_key, 0) + 1
                else:
                    summary.candidates_quarantined += 1
                    reason_key = rules_trig[0] if rules_trig else "RULE_QUARANTINED"
                    summary.quarantine_reasons_breakdown[reason_key] = summary.quarantine_reasons_breakdown.get(reason_key, 0) + 1

                logger.info(f"[FreeOnlyVerifier] Candidate '{candidate.id}' ({candidate.title[:30]}): {decision.value} | {reason}")

                # Persist to staging
                if not dry_run:
                    self.repository.update_candidate_verification(
                        candidate_id=candidate.id,
                        evaluation=evaluation,
                    )

            except Exception as e:
                err_msg = f"Unexpected error evaluating candidate '{candidate.id}': {e}"
                logger.error(err_msg, exc_info=True)
                summary.errors.append(err_msg)
                summary.candidates_quarantined += 1
                # In case of error, quarantine candidate safely
                if not dry_run:
                    safe_eval = FreeOnlyEvaluation(
                        candidate_id=candidate.id,
                        decision=FreeOnlyDecision.QUARANTINED,
                        pricing_verification_status=PricingVerificationStatus.UNCERTAIN,
                        is_free=None,
                        participant_cost_status="UNCERTAIN",
                        participant_compensation_status="UNKNOWN",
                        mandatory_fee_status="UNKNOWN",
                        verification_reason=f"Quarantined due to evaluation error: {e}",
                        rule_version=self.rule_version,
                        rules_triggered=["RULE_ERROR_QUARANTINE"],
                    )
                    self.repository.update_candidate_verification(
                        candidate_id=candidate.id,
                        evaluation=safe_eval,
                    )

        _notify(100.0, "Free-Only Verification Completed")
        finished_time = time.time()
        summary.completed_at = datetime.now(timezone.utc).isoformat()
        summary.duration_seconds = round(finished_time - start_time, 2)
        summary.status = "completed"

        logger.info(
            f"[FreeOnlyVerifier] Verification finished in {summary.duration_seconds}s | "
            f"Evaluated: {summary.candidates_evaluated} | "
            f"APPROVED: {summary.candidates_approved} | "
            f"REJECTED: {summary.candidates_rejected} | "
            f"QUARANTINED: {summary.candidates_quarantined}"
        )
        return summary

