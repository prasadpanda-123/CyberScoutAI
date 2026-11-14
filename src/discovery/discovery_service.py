"""
Global Discovery Service Orchestrator for CyberScout AI.

Coordinates query planning, Tavily search execution, URL security validation,
duplicate filtering, and candidate staging across India and global regions.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import uuid

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.client_tavily import (
    TavilyAPIError,
    TavilyAuthError,
    TavilyBudgetExceededError,
    TavilyClient,
    TavilyRateLimitError,
    TavilyTimeoutError,
    sanitize_secret,
)
from src.discovery.discovery_models import (
    CandidateProcessingStatus,
    DiscoveredCandidate,
    DiscoveryBudget,
    DiscoveryRunSummary,
    GeographicRegion,
    OpportunityCategory,
    PricingVerificationStatus,
    SearchQuerySpec,
)
from src.discovery.platform_registry import PlatformRegistry
from src.discovery.query_planner import DiscoveryQueryPlanner
from src.discovery.region_registry import RegionRegistry
from src.discovery.url_validator import URLValidator

logger = get_logger(__name__)


class GlobalDiscoveryService:
    """
    Master service coordinating automated opportunity discovery via Tavily Search API.
    """

    def __init__(
        self,
        tavily_client: Optional[TavilyClient] = None,
        query_planner: Optional[DiscoveryQueryPlanner] = None,
        url_validator: Optional[URLValidator] = None,
        candidate_repo: Optional[DiscoveredCandidateRepository] = None,
        db_manager: Optional[DatabaseManager] = None,
        budget: Optional[DiscoveryBudget] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.budget = budget or DiscoveryBudget()
        self.tavily_client = tavily_client or TavilyClient(budget=self.budget)
        self.query_planner = query_planner or DiscoveryQueryPlanner()
        self.url_validator = url_validator or URLValidator(resolve_dns=False)
        self.candidate_repo = candidate_repo or DiscoveredCandidateRepository(db_manager=self.db_manager)
        self.platform_registry = PlatformRegistry()
        self.region_registry = RegionRegistry()

    def run_discovery(
        self,
        run_id: Optional[str] = None,
        max_queries: Optional[int] = None,
        prioritize_india: bool = True,
        dry_run: bool = False,
        progress_callback: Optional[Any] = None,
    ) -> DiscoveryRunSummary:
        """
        Executes a complete global discovery cycle:
        1. Acquire execution lock to prevent overlapping runs.
        2. Plan prioritized multi-region queries (India first, then global).
        3. Execute Tavily search queries respecting budget limits.
        4. Validate candidate URLs against SSRF & dangerous protocols.
        5. Deduplicate against live opportunities and staged candidates.
        6. Stage new verified candidates into DiscoveredCandidates repository.
        7. Compile and return DiscoveryRunSummary.

        Args:
            run_id: Optional tracking identifier. Generated if not provided.
            max_queries: Optional override for query count limit (capped by budget).
            prioritize_india: If True, allocates top query slots to India.
            dry_run: If True, bypasses database staging and external API writes.
            progress_callback: Optional callable for progress telemetry (pct, msg).

        Returns:
            DiscoveryRunSummary containing execution statistics and metrics.
        """
        start_time = time.time()
        active_run_id = run_id or f"disc-{uuid.uuid4()}"
        started_iso = datetime.now(timezone.utc).isoformat()

        logger.info(f"================================================================")
        logger.info(f"[DiscoveryService] Starting Global AI Discovery Run: {active_run_id}")
        logger.info(f"================================================================")

        summary = DiscoveryRunSummary(
            run_id=active_run_id,
            started_at=started_iso,
        )

        def _notify(pct: float, msg: str):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        _notify(5.0, "Checking Concurrency Locks")

        # 1. Concurrency Protection Check
        if not dry_run:
            from src.automation.job_manager import scan_job_manager
            if scan_job_manager.is_scan_active():
                err_msg = "Another scan or discovery operation is already active."
                logger.warning(f"[DiscoveryService] Run {active_run_id} aborted: {err_msg}")
                summary.status = "conflict"
                summary.errors.append(err_msg)
                summary.completed_at = datetime.now(timezone.utc).isoformat()
                summary.duration_seconds = round(time.time() - start_time, 2)
                return summary

        # 2. Plan Queries
        _notify(10.0, "Planning Multi-Region Query Matrix")
        effective_max = min(max_queries or self.budget.max_searches_per_run, self.budget.max_searches_per_run)
        query_specs: List[SearchQuerySpec] = self.query_planner.build_search_plan(
            max_queries=effective_max,
            prioritize_india=prioritize_india,
        )
        summary.queries_planned = len(query_specs)
        logger.info(f"[DiscoveryService] Planned {len(query_specs)} search queries (India prioritized: {prioritize_india}).")

        # 3. Check Tavily Client Readiness
        if not self.tavily_client.is_configured and not dry_run:
            err = "TAVILY_API_KEY is missing or invalid. Discovery cannot proceed."
            logger.error(f"[DiscoveryService] {err}")
            summary.status = "failed"
            summary.errors.append(err)
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        candidates_to_stage: List[DiscoveredCandidate] = []
        seen_run_hashes: set = set()

        # 4. Execute Search Queries
        total_queries = len(query_specs) or 1
        for idx, spec in enumerate(query_specs):
            step_pct = 15.0 + ((idx / total_queries) * 65.0)
            _notify(step_pct, f"Searching: {spec.region.value} - {spec.category.value}")

            logger.info(f"[DiscoveryService] Query ({idx + 1}/{total_queries}) [{spec.region.value}]: {sanitize_secret(spec.query)}")

            if dry_run:
                summary.queries_executed += 1
                continue

            try:
                raw_results = self.tavily_client.execute_query_spec(spec)
                summary.queries_executed += 1
                summary.candidates_found_raw += len(raw_results)

                for item in raw_results:
                    raw_url = item.get("url", "").strip()
                    if not raw_url:
                        continue

                    # 4.1 URL Security & SSRF Validation
                    val_res = self.url_validator.validate(raw_url)
                    if not val_res.is_valid:
                        logger.debug(f"[DiscoveryService] URL rejected by security guard: {val_res.rejection_reason} ({raw_url})")
                        summary.candidates_rejected_security += 1
                        continue

                    # 4.2 Deduplication: Check in-run duplicates
                    if val_res.url_hash in seen_run_hashes:
                        summary.candidates_duplicates += 1
                        continue

                    # 4.3 Deduplication: Check approved Opportunities table
                    if self.candidate_repo.is_url_in_approved_opportunities(val_res.url_hash):
                        logger.debug(f"[DiscoveryService] Candidate already active in Opportunities: {val_res.canonical_url}")
                        summary.candidates_duplicates += 1
                        continue

                    # 4.4 Deduplication: Check existing DiscoveredCandidates table
                    if self.candidate_repo.is_url_already_discovered(val_res.url_hash):
                        summary.candidates_duplicates += 1
                        continue

                    seen_run_hashes.add(val_res.url_hash)

                    # 4.5 Platform & Geographic Detection
                    detected_platform = spec.target_platform or self.platform_registry.identify_platform(val_res.canonical_url)
                    detected_region = spec.region
                    if detected_region == GeographicRegion.GLOBAL_REMOTE:
                        # Attempt finer detection from text snippet
                        detected_region = self.region_registry.detect_region(
                            text=f"{item.get('title', '')} {item.get('content', '')}",
                            domain=val_res.domain,
                        )

                    # 4.6 Instantiate Staged Candidate
                    candidate = DiscoveredCandidate(
                        discovery_run_id=active_run_id,
                        search_query=spec.query,
                        search_provider="tavily",
                        original_url=raw_url,
                        canonical_url=val_res.canonical_url,
                        url_hash=val_res.url_hash,
                        title=item.get("title", "Untitled Opportunity").strip(),
                        snippet=item.get("content", "").strip(),
                        source_domain=val_res.domain,
                        platform_name=detected_platform,
                        country_or_scope=detected_region.value,
                        category=spec.category.value,
                        score=float(item.get("score") or 0.0),
                        pricing_verification_status=PricingVerificationStatus.UNCERTAIN.value,
                        is_free=None,  # Zero trust: never assumed free without verification!
                        processing_status=CandidateProcessingStatus.READY_FOR_EXTRACTION.value,
                        metadata={
                            "tavily_score": item.get("score"),
                            "query_region": spec.region.value,
                            "query_category": spec.category.value,
                        },
                    )

                    candidates_to_stage.append(candidate)
                    summary.candidates_valid += 1

                    # Track breakdowns
                    reg_key = detected_region.value
                    cat_key = spec.category.value
                    summary.candidates_by_region[reg_key] = summary.candidates_by_region.get(reg_key, 0) + 1
                    summary.candidates_by_category[cat_key] = summary.candidates_by_category.get(cat_key, 0) + 1
                    if detected_platform:
                        summary.candidates_by_platform[detected_platform] = summary.candidates_by_platform.get(detected_platform, 0) + 1

            except TavilyBudgetExceededError as be:
                logger.warning(f"[DiscoveryService] Search budget limit reached: {be}")
                summary.errors.append(str(be))
                summary.status = "budget_exceeded"
                break

            except TavilyRateLimitError as rle:
                logger.error(f"[DiscoveryService] Rate limit error on query: {rle}")
                summary.queries_failed += 1
                summary.errors.append(str(rle))
                continue

            except TavilyAPIError as ape:
                logger.error(f"[DiscoveryService] Tavily API error on query: {ape}")
                summary.queries_failed += 1
                summary.errors.append(str(ape))
                continue

            except Exception as ex:
                logger.error(f"[DiscoveryService] Unexpected error on query: {ex}", exc_info=True)
                summary.queries_failed += 1
                summary.errors.append(sanitize_secret(str(ex)))
                continue

        # 5. Persist Candidates
        _notify(85.0, f"Persisting {len(candidates_to_stage)} Valid Candidates")
        if not dry_run and candidates_to_stage:
            try:
                new_saved, dups_skipped = self.candidate_repo.save_candidates_batch(candidates_to_stage)
                logger.info(f"[DiscoveryService] Successfully staged {new_saved} new candidates ({dups_skipped} duplicates skipped).")
            except Exception as pe:
                logger.error(f"[DiscoveryService] Candidate persistence failure: {pe}")
                summary.errors.append(f"Persistence error: {pe}")

        # 6. Finalize Summary
        _notify(100.0, "Discovery Completed")
        finished_time = time.time()
        summary.completed_at = datetime.now(timezone.utc).isoformat()
        summary.duration_seconds = round(finished_time - start_time, 2)

        if summary.status != "budget_exceeded":
            summary.status = "completed" if summary.queries_failed == 0 else "partial"

        logger.info(f"================================================================")
        logger.info(f"[DiscoveryService] Run Complete: {summary.candidates_valid} valid candidates discovered in {summary.duration_seconds}s")
        logger.info(f"Raw: {summary.candidates_found_raw} | Security Rejected: {summary.candidates_rejected_security} | Duplicates: {summary.candidates_duplicates}")
        logger.info(f"================================================================")

        return summary

