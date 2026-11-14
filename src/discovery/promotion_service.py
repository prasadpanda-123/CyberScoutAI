"""
Controlled Production Promotion Service for CyberScout AI (Phase F).

Enforces authoritative Python approval gates, layered deduplication,
deterministic priority ranking, and transactional atomic promotion
from DiscoveredCandidates into production Opportunities.
"""

from datetime import datetime, timezone
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

from src.core.exceptions import RepositoryError
from src.core.logging import get_logger
from src.discovery.opportunity_ranker import OpportunityRanker
from src.discovery.production_deduplication import ProductionDeduplicator
from src.discovery.promotion_models import (
    CandidatePromotionEvaluation,
    OpportunityFieldValidationResult,
    PromotionDecision,
    PromotionRunSummary,
    PromotionStatus,
)
from src.discovery.promotion_repository import PromotionRepository
from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity
from src.utils.url_utils import is_valid_url, normalize_url

logger = get_logger(__name__)


class ProductionPromotionService:
    """
    Master service coordinating candidate approval verification, deduplication,
    ranking, and atomic transactional promotion into production Opportunities.
    """

    def __init__(
        self,
        repository: Optional[PromotionRepository] = None,
        deduplicator: Optional[ProductionDeduplicator] = None,
        ranker: Optional[OpportunityRanker] = None,
        dry_run: Optional[bool] = None,
        enabled: Optional[bool] = None,
    ):
        self.repository = repository or PromotionRepository()
        self.deduplicator = deduplicator or ProductionDeduplicator()
        self.ranker = ranker or OpportunityRanker()

        # Load configurations: default to safe dry_run=True, enabled=False
        env_dry = os.getenv("PROMOTION_DRY_RUN")
        if dry_run is not None:
            self.dry_run = dry_run
        elif env_dry is not None:
            self.dry_run = env_dry.strip().lower() in ("true", "1", "yes")
        else:
            self.dry_run = True

        env_enabled = os.getenv("PROMOTION_ENABLED")
        if enabled is not None:
            self.enabled = enabled
        elif env_enabled is not None:
            self.enabled = env_enabled.strip().lower() in ("true", "1", "yes")
        else:
            self.enabled = False

    def validate_candidate_fields(self, candidate_data: Dict[str, Any]) -> OpportunityFieldValidationResult:
        """
        Validates that candidate satisfies all minimum required fields before promotion.
        """
        missing = []
        errors = []

        title = str(candidate_data.get("title") or "").strip()
        if not title or len(title) < 3:
            missing.append("title")
            errors.append("Title is missing or shorter than 3 characters.")

        url = candidate_data.get("canonical_url") or candidate_data.get("original_url") or ""
        if not url or not is_valid_url(url):
            missing.append("url")
            errors.append(f"Invalid or unsafe target URL: '{url}'.")

        category = str(candidate_data.get("category") or "").strip().lower()
        valid_cats = {c.value.lower() for c in OpportunityCategory} | {
            "internship", "job", "ctf", "bug_bounty", "vdp", "course",
            "certification", "hackathon", "scholarship", "fellowship", "other"
        }
        if not category or category not in valid_cats:
            category = "other"

        desc = (candidate_data.get("description") or candidate_data.get("snippet") or "").strip()
        if not desc or len(desc) < 10:
            missing.append("description")
            errors.append("Description/snippet is missing or shorter than 10 characters.")

        # Check expiration date if present
        deadline_str = candidate_data.get("deadline")
        if deadline_str:
            try:
                dl_date = datetime.strptime(str(deadline_str).strip()[:10], "%Y-%m-%d").date()
                today = datetime.now(timezone.utc).date()
                if dl_date < today:
                    errors.append(f"Opportunity deadline '{deadline_str}' has already expired.")
            except Exception:
                pass

        is_valid = len(missing) == 0 and not any("expired" in err for err in errors)
        return OpportunityFieldValidationResult(
            is_valid=is_valid,
            missing_fields=missing,
            errors=errors,
        )

    def evaluate_candidate_for_promotion(
        self,
        candidate_row: Dict[str, Any],
        existing_opportunities: List[Opportunity],
    ) -> CandidatePromotionEvaluation:
        """
        Executes Part 2 (Approval Gate) and Part 3 (Deduplication) evaluation.
        """
        cid = candidate_row.get("id") or "unknown"
        title = candidate_row.get("title") or "Untitled"
        url = candidate_row.get("canonical_url") or candidate_row.get("original_url") or ""
        metadata_str = candidate_row.get("metadata") or "{}"
        metadata: Dict[str, Any] = {}
        if isinstance(metadata_str, str):
            try:
                metadata = json.loads(metadata_str)
            except Exception:
                metadata = {}
        elif isinstance(metadata_str, dict):
            metadata = metadata_str

        # 1. Gate Check 1: FreeOnlyDecision == APPROVED
        decision_val = candidate_row.get("free_only_decision")
        meta_verif = metadata.get("free_only_verification") or {}
        meta_decision = meta_verif.get("decision")
        if decision_val != "APPROVED" or meta_decision != "APPROVED":
            blocked_type = PromotionDecision.BLOCKED_REJECTED if decision_val == "REJECTED" else PromotionDecision.BLOCKED_QUARANTINED
            reason = f"Candidate blocked: Free-only verification decision is '{decision_val}' (must be APPROVED)."
            return CandidatePromotionEvaluation(
                candidate_id=cid,
                title=title,
                canonical_url=url,
                decision=blocked_type,
                reason=reason,
            )

        # 2. Gate Check 2: Pricing Verification Status == VERIFIED_FREE
        pricing_status = candidate_row.get("pricing_verification_status") or meta_verif.get("pricing_verification_status")
        if pricing_status != "VERIFIED_FREE":
            return CandidatePromotionEvaluation(
                candidate_id=cid,
                title=title,
                canonical_url=url,
                decision=PromotionDecision.BLOCKED_QUARANTINED,
                reason=f"Candidate blocked: Pricing status is '{pricing_status}' (must be VERIFIED_FREE).",
            )

        # 3. Gate Check 3: Already promoted?
        already_promoted_id = candidate_row.get("promoted_to_opportunity_id")
        prom_status = candidate_row.get("promotion_status")
        if already_promoted_id or prom_status in (PromotionStatus.PROMOTED.value, PromotionStatus.UPDATED.value):
            return CandidatePromotionEvaluation(
                candidate_id=cid,
                title=title,
                canonical_url=url,
                decision=PromotionDecision.SKIPPED_DUPLICATE,
                opportunity_id=already_promoted_id,
                reason=f"Candidate already promoted to Opportunity '{already_promoted_id}'.",
            )

        # Extract structured classification fields from metadata
        classification = metadata.get("classification") or {}
        candidate_data = {
            **candidate_row,
            "title": classification.get("title") or candidate_row.get("title"),
            "organization": classification.get("organization") or candidate_row.get("platform_name") or candidate_row.get("source_domain"),
            "category": classification.get("category") or candidate_row.get("category"),
            "description": classification.get("description") or candidate_row.get("snippet"),
            "required_skills": classification.get("required_skills"),
            "eligibility_criteria": classification.get("eligibility_criteria"),
            "country_or_scope": classification.get("country_or_scope") or candidate_row.get("country_or_scope"),
            "remote": classification.get("is_remote", False),
            "deadline": classification.get("deadline"),
            "application_url": classification.get("application_url") or url,
        }

        # 4. Gate Check 4: Field and Schema Validation
        val_res = self.validate_candidate_fields(candidate_data)
        if not val_res.is_valid:
            return CandidatePromotionEvaluation(
                candidate_id=cid,
                title=title,
                canonical_url=url,
                decision=PromotionDecision.BLOCKED_INVALID,
                reason=f"Candidate failed field validation: {'; '.join(val_res.errors)}",
            )

        # 5. Gate Check 5: Layered Production Deduplication
        match_result = self.deduplicator.find_match(candidate_data, existing_opportunities)
        if match_result:
            matched_opp, match_reason = match_result
            changes = self.deduplicator.detect_meaningful_changes(candidate_data, matched_opp)
            if changes:
                # Update existing opportunity
                return CandidatePromotionEvaluation(
                    candidate_id=cid,
                    title=title,
                    canonical_url=url,
                    decision=PromotionDecision.UPDATED,
                    opportunity_id=matched_opp.id,
                    is_update=True,
                    reason=f"Matched existing Opportunity '{matched_opp.id}' ({match_reason}) with updates: {', '.join(changes)}.",
                    changes_detected=changes,
                )
            else:
                # Existing opportunity is identical; skip duplicate
                return CandidatePromotionEvaluation(
                    candidate_id=cid,
                    title=title,
                    canonical_url=url,
                    decision=PromotionDecision.SKIPPED_DUPLICATE,
                    opportunity_id=matched_opp.id,
                    reason=f"Identical opportunity already exists in production: '{matched_opp.id}' ({match_reason}).",
                )

        # 6. Candidate is Genuinely New: Calculate Deterministic Priority Score
        score, breakdown = self.ranker.calculate_score(
            candidate_data,
            source_domain=candidate_row.get("source_domain"),
        )

        return CandidatePromotionEvaluation(
            candidate_id=cid,
            title=candidate_data["title"],
            canonical_url=url,
            decision=PromotionDecision.PROMOTED,
            is_new_promotion=True,
            reason="Verified free opportunity approved for production promotion.",
            rank_score=score,
            rank_breakdown=breakdown,
        )

    def promote_candidates(
        self,
        run_id: str,
        limit: int = 50,
        dry_run: Optional[bool] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> PromotionRunSummary:
        """
        Executes controlled promotion run across all approved staged candidates.
        """
        start_time = datetime.now(timezone.utc)
        effective_dry_run = self.dry_run if dry_run is None else dry_run

        # If promotion is not enabled and dry_run was not explicitly False, force dry_run
        if not self.enabled:
            effective_dry_run = True

        summary = PromotionRunSummary(run_id=run_id, dry_run=effective_dry_run)
        logger.info(
            f"[PromotionService] Starting production promotion run '{run_id}' "
            f"(dry_run={effective_dry_run}, enabled={self.enabled})."
        )

        # 1. Fetch approved candidates awaiting promotion
        candidates = self.repository.get_approved_candidates_for_promotion(run_id=run_id, limit=limit)
        if not candidates and not run_id.startswith("test-"):
            # Check without run_id restriction to catch any pending approved candidates
            candidates = self.repository.get_approved_candidates_for_promotion(limit=limit)

        summary.candidates_evaluated = len(candidates)
        if not candidates:
            logger.info("[PromotionService] No approved candidates pending promotion.")
            summary.duration_sec = (datetime.now(timezone.utc) - start_time).total_seconds()
            return summary

        # 2. Fetch existing production opportunities for deduplication matching
        existing_opps = self.repository.get_existing_production_opportunities(limit=500)
        total = len(candidates)

        for idx, cand_row in enumerate(candidates):
            cid = cand_row.get("id") or f"cand_{idx}"
            if progress_callback:
                pct = ((idx + 1) / total) * 100.0
                progress_callback(pct, f"Evaluating candidate {idx+1}/{total} for promotion")

            evaluation = self.evaluate_candidate_for_promotion(cand_row, existing_opps)
            summary.evaluations.append(evaluation)

            if evaluation.decision == PromotionDecision.PROMOTED:
                if effective_dry_run:
                    evaluation.decision = PromotionDecision.DRY_RUN
                    summary.candidates_promoted += 1
                    simulated_id = f"sim_{uuid.uuid4().hex[:12]}"
                    evaluation.opportunity_id = simulated_id
                    summary.promoted_opportunity_ids.append(simulated_id)
                else:
                    # Construct Opportunity entity
                    opp = self._build_opportunity_from_candidate(cand_row, evaluation)
                    try:
                        promoted_id = self.repository.promote_candidate_transactional(
                            candidate_id=cid,
                            opportunity=opp,
                            is_update=False,
                        )
                        evaluation.opportunity_id = promoted_id
                        summary.candidates_promoted += 1
                        summary.promoted_opportunity_ids.append(promoted_id)
                        existing_opps.append(opp)
                    except Exception as e:
                        logger.error(f"[PromotionService] Error promoting candidate '{cid}': {e}")
                        summary.errors_count += 1

            elif evaluation.decision == PromotionDecision.UPDATED:
                if effective_dry_run:
                    summary.existing_updated += 1
                    summary.updated_opportunity_ids.append(evaluation.opportunity_id or "")
                else:
                    # Update existing opportunity
                    existing_match = next((o for o in existing_opps if o.id == evaluation.opportunity_id), None)
                    if existing_match:
                        self._apply_updates_to_opportunity(existing_match, cand_row, evaluation.changes_detected)
                        try:
                            self.repository.promote_candidate_transactional(
                                candidate_id=cid,
                                opportunity=existing_match,
                                is_update=True,
                                update_fields=evaluation.changes_detected,
                            )
                            summary.existing_updated += 1
                            summary.updated_opportunity_ids.append(existing_match.id)
                        except Exception as e:
                            logger.error(f"[PromotionService] Error updating opportunity '{existing_match.id}': {e}")
                            summary.errors_count += 1

            elif evaluation.decision == PromotionDecision.SKIPPED_DUPLICATE:
                summary.duplicates_skipped += 1
                if not effective_dry_run:
                    self.repository.mark_candidate_promotion_status(
                        candidate_id=cid,
                        status=PromotionStatus.SKIPPED,
                        reason=evaluation.reason,
                    )

            elif evaluation.decision in (PromotionDecision.BLOCKED_REJECTED, PromotionDecision.BLOCKED_QUARANTINED):
                summary.blocked_unapproved += 1
                if not effective_dry_run:
                    self.repository.mark_candidate_promotion_status(
                        candidate_id=cid,
                        status=PromotionStatus.BLOCKED,
                        reason=evaluation.reason,
                    )

            elif evaluation.decision == PromotionDecision.BLOCKED_INVALID:
                summary.blocked_invalid += 1
                if not effective_dry_run:
                    self.repository.mark_candidate_promotion_status(
                        candidate_id=cid,
                        status=PromotionStatus.BLOCKED,
                        reason=evaluation.reason,
                    )

        summary.duration_sec = round((datetime.now(timezone.utc) - start_time).total_seconds(), 2)
        logger.info(
            f"[PromotionService] Promotion complete: {summary.candidates_promoted} promoted, "
            f"{summary.existing_updated} updated, {summary.duplicates_skipped} duplicates skipped, "
            f"{summary.blocked_unapproved} unapproved blocked in {summary.duration_sec}s."
        )
        return summary

    def _build_opportunity_from_candidate(
        self,
        candidate_row: Dict[str, Any],
        evaluation: CandidatePromotionEvaluation,
    ) -> Opportunity:
        """Constructs an authoritative Opportunity entity from candidate data."""
        metadata_str = candidate_row.get("metadata") or "{}"
        metadata: Dict[str, Any] = {}
        if isinstance(metadata_str, str):
            try:
                metadata = json.loads(metadata_str)
            except Exception:
                metadata = {}
        elif isinstance(metadata_str, dict):
            metadata = metadata_str

        cls_data = metadata.get("classification") or {}
        free_verif = metadata.get("free_only_verification") or {}

        title = cls_data.get("title") or candidate_row.get("title") or "Cybersecurity Opportunity"
        url = candidate_row.get("canonical_url") or candidate_row.get("original_url") or ""
        app_url = cls_data.get("application_url") or url
        org = cls_data.get("organization") or candidate_row.get("platform_name") or candidate_row.get("source_domain")
        cat = (cls_data.get("category") or candidate_row.get("category") or "other").lower()
        desc = cls_data.get("description") or candidate_row.get("snippet") or ""
        skills = cls_data.get("required_skills") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        opp = Opportunity(
            id=str(uuid.uuid4()),
            title=title,
            url=app_url,
            canonical_url=normalize_url(url),
            source_id="tavily",
            category=cat,
            provider=org,
            company=org,
            location=cls_data.get("country_or_scope") or candidate_row.get("country_or_scope") or "Global",
            remote=bool(cls_data.get("is_remote", False)),
            paid=False,
            is_free=True,
            pricing_type="free",
            deadline=cls_data.get("deadline"),
            eligibility=cls_data.get("eligibility_criteria"),
            requirements=", ".join(skills) if skills else None,
            tags=skills,
            score=evaluation.rank_score,
            score_breakdown=evaluation.rank_breakdown,
            description=desc,
            verification_status="verified",
            status=Status.ACTIVE.value,
            lifecycle_status="active",
            quality_status="passed",
            discovered_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            raw_data={
                "candidate_id": candidate_row.get("id"),
                "discovery_run_id": candidate_row.get("discovery_run_id"),
                "source_domain": candidate_row.get("source_domain"),
                "platform_name": candidate_row.get("platform_name"),
                "classification": cls_data,
                "free_only_verification": free_verif,
            },
        )
        return opp

    @staticmethod
    def _apply_updates_to_opportunity(
        existing_opp: Opportunity,
        candidate_row: Dict[str, Any],
        changes: List[str],
    ) -> None:
        """Applies verified non-destructive updates to existing Opportunity entity."""
        metadata_str = candidate_row.get("metadata") or "{}"
        metadata: Dict[str, Any] = {}
        if isinstance(metadata_str, str):
            try:
                metadata = json.loads(metadata_str)
            except Exception:
                metadata = {}
        elif isinstance(metadata_str, dict):
            metadata = metadata_str

        cls_data = metadata.get("classification") or {}
        if "deadline" in changes and cls_data.get("deadline"):
            existing_opp.deadline = cls_data["deadline"]

        if "description" in changes and cls_data.get("description"):
            existing_opp.description = cls_data["description"]

        if "requirements" in changes and cls_data.get("required_skills"):
            skills = cls_data["required_skills"]
            if isinstance(skills, list):
                existing_opp.tags = skills
                existing_opp.requirements = ", ".join(skills)
            elif isinstance(skills, str):
                existing_opp.requirements = skills

        if "remote" in changes and "is_remote" in cls_data:
            existing_opp.remote = bool(cls_data["is_remote"])

        existing_opp.last_seen_at = datetime.now(timezone.utc).isoformat()
        existing_opp.last_harvested_at = datetime.now(timezone.utc).isoformat()

