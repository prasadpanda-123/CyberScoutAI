"""
AI Opportunity Classification Master Service for CyberScout AI (Phase D).

Orchestrates multi-provider opportunity classification with:
- Groq API as the primary high-throughput classification provider.
- Google Gemini API as the resilient fallback provider.
- Independent Python schema and evidence validation.
- Idempotent candidate staging persistence in PostgreSQL DiscoveredCandidates.
- Complete isolation from production Opportunities table.
"""

from datetime import datetime, timezone
import os
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.classification_models import (
    ClassificationBudget,
    ClassificationResult,
    ClassificationRunSummary,
)
from src.discovery.classification_repository import ClassificationRepository
from src.discovery.classification_schema import (
    AI_CLASSIFICATION_PROMPT_VERSION,
    CLASSIFICATION_SYSTEM_PROMPT,
    build_classification_user_prompt,
)
from src.discovery.classification_validator import ClassificationValidator
from src.discovery.client_gemini import GeminiClient, GeminiError
from src.discovery.client_groq import GroqClient, GroqError
from src.discovery.discovery_models import DiscoveredCandidate

logger = get_logger(__name__)


class AIClassificationService:
    """
    Master AI classification service coordinating Groq and Gemini providers
    to classify opportunities discovered by Tavily and extracted by Firecrawl.
    """

    def __init__(
        self,
        groq_client: Optional[GroqClient] = None,
        gemini_client: Optional[GeminiClient] = None,
        validator: Optional[ClassificationValidator] = None,
        classification_repo: Optional[ClassificationRepository] = None,
        db_manager: Optional[DatabaseManager] = None,
        budget: Optional[ClassificationBudget] = None,
        prompt_version: str = AI_CLASSIFICATION_PROMPT_VERSION,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.budget = budget or ClassificationBudget()
        self.groq_client = groq_client or GroqClient(budget=self.budget)
        self.gemini_client = gemini_client or GeminiClient(budget=self.budget)
        self.validator = validator or ClassificationValidator()
        self.classification_repo = classification_repo or ClassificationRepository(
            db_manager=self.db_manager
        )
        self.prompt_version = prompt_version

        # Configurable provider order
        self.primary_provider = os.getenv("AI_PRIMARY_PROVIDER", "groq").lower()
        self.fallback_provider = os.getenv("AI_FALLBACK_PROVIDER", "gemini").lower()
        self.is_enabled = os.getenv("AI_CLASSIFICATION_ENABLED", "true").lower() in ("true", "1", "yes")

    def run_classification(
        self,
        candidates: Optional[List[DiscoveredCandidate]] = None,
        max_candidates: Optional[int] = None,
        run_id: Optional[str] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> ClassificationRunSummary:
        """
        Executes AI classification across staged candidates with extracted content.

        Workflow:
        1. Query candidates from DiscoveredCandidates where extraction_status='completed'
        2. Format bounded system prompt and opportunity content
        3. Attempt primary classification via Groq
        4. Validate Groq output against JSON Schema and verbatim source evidence
        5. If Groq fails/times out/returns invalid JSON, attempt fallback via Gemini
        6. Validate Gemini output against identical schema and evidence rules
        7. If both fail, record error in candidate staging metadata without crashing
        8. Persist validated classification in DiscoveredCandidates staging table
        9. Return structured ClassificationRunSummary
        """
        start_time = time.time()
        active_run_id = run_id or f"classify-{uuid.uuid4()}"
        started_iso = datetime.now(timezone.utc).isoformat()

        logger.info("================================================================")
        logger.info(f"[ClassificationService] Starting AI Opportunity Classification: {active_run_id}")
        logger.info("================================================================")

        summary = ClassificationRunSummary(
            run_id=active_run_id,
            started_at=started_iso,
        )

        def _notify(pct: float, msg: str):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        # 1. Check Configuration
        if not self.is_enabled:
            logger.info("[ClassificationService] AI classification is disabled via configuration. Skipping.")
            summary.status = "disabled"
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        has_any_provider = self.groq_client.is_configured or self.gemini_client.is_configured
        if not has_any_provider and not dry_run:
            msg = "Neither GROQ_API_KEY nor GEMINI_API_KEY is configured. Classification cannot proceed."
            logger.warning(f"[ClassificationService] {msg}")
            summary.status = "skipped_missing_credentials"
            summary.errors.append(msg)
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        # 2. Select Staged Candidates
        effective_limit = min(
            max_candidates or self.budget.max_classifications_per_run,
            self.budget.max_classifications_per_run,
        )

        if candidates is not None:
            target_candidates = candidates[:effective_limit]
        else:
            target_candidates = self.classification_repo.get_candidates_for_classification(limit=effective_limit)

        summary.candidates_attempted = len(target_candidates)
        logger.info(f"[ClassificationService] Selected {len(target_candidates)} candidates for AI classification.")

        if not target_candidates:
            summary.status = "completed"
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        total_candidates = len(target_candidates)

        for idx, candidate in enumerate(target_candidates):
            step_pct = 10.0 + ((idx / total_candidates) * 80.0)
            _notify(step_pct, f"Classifying ({idx + 1}/{total_candidates}): {candidate.title[:40]}")

            # Extract page content from Firecrawl extraction metadata
            extraction_meta = candidate.metadata.get("extraction") or {}
            page_content = (
                extraction_meta.get("main_content_markdown")
                or extraction_meta.get("short_description")
                or candidate.snippet
                or candidate.title
            )

            user_prompt = build_classification_user_prompt(
                url=candidate.canonical_url or candidate.original_url,
                title=candidate.title,
                category_hint=candidate.category,
                page_content=page_content,
                metadata={
                    "source_domain": candidate.source_domain,
                    "platform_name": candidate.platform_name,
                },
            )

            classified_result: Optional[ClassificationResult] = None
            provider_errors: List[str] = []

            # Step A: Primary Provider (Groq)
            if self.groq_client.is_configured or dry_run:
                try:
                    logger.debug(f"[ClassificationService] Attempting primary classification via Groq for '{candidate.id}'")
                    groq_raw = self.groq_client.classify(
                        system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                    )
                    is_valid, val_errors, res = self.validator.validate(
                        raw_output=groq_raw,
                        candidate_id=candidate.id,
                        source_url=candidate.canonical_url,
                        source_content=page_content,
                        provider="groq",
                        model=self.groq_client.model,
                        prompt_version=self.prompt_version,
                    )
                    if is_valid and res:
                        classified_result = res
                        summary.candidates_classified_groq += 1
                        logger.info(f"[ClassificationService] Successfully classified via Groq: '{res.title}' -> {res.category}")
                    else:
                        logger.warning(f"[ClassificationService] Groq output validation failed for '{candidate.id}': {val_errors}")
                        summary.candidates_rejected_validation += 1
                        provider_errors.append(f"Groq validation: {'; '.join(val_errors)}")
                except GroqError as ge:
                    logger.warning(f"[ClassificationService] Groq primary provider failed for '{candidate.id}': {ge}")
                    provider_errors.append(f"Groq error: {str(ge)}")
                except Exception as unexp_ge:
                    logger.error(f"[ClassificationService] Unexpected error on Groq for '{candidate.id}': {unexp_ge}")
                    provider_errors.append(f"Groq unexpected: {str(unexp_ge)}")

            # Step B: Fallback Provider (Gemini) if Groq failed or produced invalid output
            if classified_result is None and (self.gemini_client.is_configured or dry_run):
                try:
                    logger.info(f"[ClassificationService] Invoking Gemini fallback for candidate '{candidate.id}'...")
                    gemini_raw = self.gemini_client.classify(
                        system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                    )
                    is_valid, val_errors, res = self.validator.validate(
                        raw_output=gemini_raw,
                        candidate_id=candidate.id,
                        source_url=candidate.canonical_url,
                        source_content=page_content,
                        provider="gemini",
                        model=self.gemini_client.model,
                        prompt_version=self.prompt_version,
                    )
                    if is_valid and res:
                        classified_result = res
                        summary.candidates_classified_gemini += 1
                        logger.info(f"[ClassificationService] Successfully classified via Gemini fallback: '{res.title}' -> {res.category}")
                    else:
                        logger.warning(f"[ClassificationService] Gemini output validation failed for '{candidate.id}': {val_errors}")
                        summary.candidates_rejected_validation += 1
                        provider_errors.append(f"Gemini validation: {'; '.join(val_errors)}")
                except GeminiError as gme:
                    logger.warning(f"[ClassificationService] Gemini fallback failed for '{candidate.id}': {gme}")
                    provider_errors.append(f"Gemini error: {str(gme)}")
                except Exception as unexp_gme:
                    logger.error(f"[ClassificationService] Unexpected error on Gemini for '{candidate.id}': {unexp_gme}")
                    provider_errors.append(f"Gemini unexpected: {str(unexp_gme)}")

            # Step C: Persist outcome
            if classified_result is not None:
                if not dry_run:
                    self.classification_repo.update_candidate_classification(
                        candidate_id=candidate.id,
                        result=classified_result,
                    )
            else:
                summary.candidates_failed += 1
                err_summary = "; ".join(provider_errors) or "All classification providers failed"
                summary.errors.append(f"Candidate {candidate.id}: {err_summary}")
                logger.warning(f"[ClassificationService] All AI providers failed for '{candidate.id}'. Staging as failed for retry.")
                if not dry_run:
                    self.classification_repo.mark_classification_failed(
                        candidate_id=candidate.id,
                        error_reason=err_summary,
                        provider_errors=provider_errors,
                    )

        _notify(100.0, "AI Opportunity Classification Completed")
        finished_time = time.time()
        summary.completed_at = datetime.now(timezone.utc).isoformat()
        summary.duration_seconds = round(finished_time - start_time, 2)
        summary.status = "completed" if summary.candidates_failed == 0 else "partial"

        logger.info(
            f"[ClassificationService] Classification finished in {summary.duration_seconds}s | "
            f"Attempted: {summary.candidates_attempted} | "
            f"Groq: {summary.candidates_classified_groq} | "
            f"Gemini: {summary.candidates_classified_gemini} | "
            f"Failed: {summary.candidates_failed} | "
            f"Validation Rejected: {summary.candidates_rejected_validation}"
        )
        return summary

