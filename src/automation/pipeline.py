"""
Automated Pipeline Runner for CyberScout AI.

Provides the single source of truth scan execution function `run_pipeline_once()`
used identically by the CLI, Web Dashboard REST API (`POST /api/run`), and Daily Scheduler.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import uuid

from src.core.exceptions import DatabaseConnectionError
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.knowledge_manager import KnowledgeManager
from src.collectors.manager import CollectorManager
from src.intelligence.search_planner import SearchPlanner
from src.intelligence.ranking_engine import RankingEngine
from src.intelligence.quality_engine import QualityEngine
from src.intelligence.production.production_engine import ProductionEngine
from src.models.opportunity import Opportunity
from src.processors.pipeline import ProcessingPipeline
from src.notifier.email_client import EmailClient
from src.automation.metrics import RunMetrics
from src.intelligence.data_quality_engine import DataQualityEngine
from src.intelligence.lifecycle_engine import LifecycleEngine
from src.intelligence.source_anomaly_detector import SourceAnomalyDetector

logger = get_logger(__name__)


def extract_normalized_description(item: Any) -> str:
    """
    Normalizes description from multiple potential payload fields before validation:
    description OR summary OR content OR body OR readme OR text OR title.
    """
    if isinstance(item, Opportunity):
        if item.description and item.description.strip():
            return item.description.strip()
        raw = getattr(item, "raw_data", {}) or {}
        if not isinstance(raw, dict):
            raw = {}
        for field in ["description", "summary", "content", "body", "readme", "text", "title"]:
            val = raw.get(field) or getattr(item, field, None)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return item.title or "Cybersecurity Opportunity"
    elif isinstance(item, dict):
        for field in ["description", "summary", "content", "body", "readme", "text", "title"]:
            val = item.get(field)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return item.get("title") or "Cybersecurity Opportunity"
    return "Cybersecurity Opportunity"


def run_pipeline_once(
    dry_run: bool = False,
    send_email: bool = False,
    db_manager: Optional[DatabaseManager] = None,
    search_planner: Optional[SearchPlanner] = None,
    collector_manager: Optional[CollectorManager] = None,
    processing_pipeline: Optional[ProcessingPipeline] = None,
    quality_engine: Optional[QualityEngine] = None,
    production_engine: Optional[ProductionEngine] = None,
    ranking_engine: Optional[RankingEngine] = None,
    knowledge_manager: Optional[KnowledgeManager] = None,
    email_client: Optional[EmailClient] = None,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Single source of truth scanning pipeline function.

    Performs the complete 10-stage scan sequence:
    Initialization -> Planning -> Resilient Collection -> Coercion & Description Normalization
    -> Deduplication & Processing -> Quality Evaluation -> Production Validation -> Ranking
    -> Knowledge Base Database Saving -> Optional Email Digest -> Log Summary & Return API JSON.

    Args:
        dry_run: If True, bypasses database persistence and email sending.
        send_email: If True, dispatches notification email digest after scan.
        db_manager: Optional DatabaseManager instance.
        progress_callback: Optional progress update callback (stage, pct, collector, found_count, err).

    Returns:
        Structured API summary response dictionary.
    """
    def _notify(stage: str, pct: float, current_col: str, count: int, err: Optional[str] = None):
        if progress_callback:
            try:
                progress_callback(stage, pct, current_col, count, err)
            except Exception:
                pass

    _notify("running", 5.0, "Initializing Database Connection", 0)
    start_time = time.time()
    started_iso = datetime.now(timezone.utc).isoformat()
    run_id = f"run-{uuid.uuid4()}"
    db = db_manager or DatabaseManager()

    if not dry_run and not db.ping():
        logger.error("Scan aborted: Database unavailable")
        _notify("failed", 0.0, "Failed", 0, "Database unavailable")
        raise DatabaseConnectionError("Scan aborted: Database unavailable. PostgreSQL connection could not be established.")

    sp = search_planner or SearchPlanner()
    cm = collector_manager or CollectorManager()
    pp = processing_pipeline or ProcessingPipeline()
    qe = quality_engine or QualityEngine()
    pe = production_engine or ProductionEngine()
    re = ranking_engine or RankingEngine()
    km = knowledge_manager or KnowledgeManager(db_manager=db)
    ec = email_client or EmailClient(db_manager=db)

    metrics = RunMetrics(run_id=run_id)

    # 1. Search Planning Phase
    _notify("running", 10.0, "Creating Search Plan", 0)
    plan_start = time.time()
    search_plan = sp.create_search_plan()
    metrics.planning_time = time.time() - plan_start

    # 2. Collection Phase with Per-Collector Resilience
    _notify("collecting", 15.0, "Starting Source Collection", 0)
    collect_start = time.time()
    collector_results = cm.execute_plan(search_plan)
    metrics.collection_time = time.time() - collect_start

    collectors_count: Dict[str, int] = {}
    collector_status: Dict[str, str] = {}
    raw_items: List[Opportunity] = []
    total_results = len(collector_results) or 1

    for idx, res in enumerate(collector_results):
        sid = getattr(res, "source_id", "unknown") or "unknown"
        errors = getattr(res, "errors", []) or []
        status_str = getattr(res, "status", "")
        succ_val = getattr(res, "success", None)
        is_succ = (status_str == "success" or succ_val is True or (not status_str and not succ_val and not errors)) and not errors
        collector_status[sid] = "success" if is_succ else "failed"

        items = getattr(res, "items", []) or []
        count = len(items)
        collectors_count[sid] = collectors_count.get(sid, 0) + count

        for item in items:
            norm_desc = extract_normalized_description(item)
            if hasattr(item, "to_opportunity"):
                try:
                    opp = item.to_opportunity()
                    if norm_desc:
                        opp.description = norm_desc
                    raw_items.append(opp)
                except Exception as dto_err:
                    logger.debug(f"Skipping unconvertible DTO item from {sid}: {dto_err}")
            elif isinstance(item, Opportunity):
                item.description = norm_desc
                raw_items.append(item)
            elif isinstance(item, dict):
                try:
                    from src.models.opportunity_dto import NormalizedOpportunityDTO
                    # If dict has raw_payload or DTO fields, convert via DTO for rich fidelity
                    dto = NormalizedOpportunityDTO.from_dict({**item, "source_id": item.get("source_id", sid)})
                    opp = dto.to_opportunity()
                    if norm_desc:
                        opp.description = norm_desc
                    raw_items.append(opp)
                except Exception:
                    try:
                        opp = Opportunity(
                            title=item.get("title", "Untitled"),
                            url=item.get("url", item.get("link", "")),
                            source_id=item.get("source_id", sid),
                            description=norm_desc,
                            category=item.get("category", "other"),
                            published_date=item.get("published", item.get("published_date", None)),
                            raw_data=item,
                        )
                        raw_items.append(opp)
                    except Exception as conv_err:
                        logger.debug(f"Skipping unconvertible item from {sid}: {conv_err}")

        pct = 15.0 + ((idx + 1) / total_results) * 45.0
        _notify("collecting", pct, f"Collected from {sid}", len(raw_items))

    # 3. Processing Phase
    _notify("processing", 65.0, "Deduplicating & Processing Raw Items", len(raw_items))
    process_start = time.time()
    processed_items = pp.process_batch(raw_items)
    metrics.processing_time = time.time() - process_start
    duplicates_removed = len(raw_items) - len(processed_items)

    # 4. Quality Intelligence & Phase 6 Data Quality Engine Evaluation Phase
    _notify("processing", 75.0, "Evaluating Quality Intelligence", len(processed_items))
    quality_start = time.time()
    quality_evaluated = qe.evaluate_batch(processed_items)

    dqe = DataQualityEngine()
    lifecycle_engine = LifecycleEngine()
    quarantined_items: List[Opportunity] = []
    dq_accepted: List[Opportunity] = []

    for opp in quality_evaluated:
        val_res = dqe.evaluate(opp)
        opp.completeness_score = val_res.completeness_score
        if val_res.is_quarantined:
            opp.quality_status = "quarantined"
            opp.quarantine_reason = val_res.quarantine_reason
            opp.is_rejected = True
            quarantined_items.append(opp)
        else:
            opp.quality_status = val_res.quality_status.value
            opp.quarantine_reason = None
            if not opp.is_rejected:
                lc_res = lifecycle_engine.evaluate(opp)
                opp.lifecycle_status = lc_res.lifecycle_status.value
                dq_accepted.append(opp)
            else:
                quarantined_items.append(opp)

    accepted_quality = dq_accepted
    rejected_items = quarantined_items
    quality_time = time.time() - quality_start

    # 5. Production Intelligence Evaluation Phase
    prod_start = time.time()
    prod_evaluated = pe.evaluate_batch(accepted_quality)
    accepted_items = [opp for opp in prod_evaluated if not opp.is_rejected]

    # 6. Ranking Phase
    _notify("processing", 85.0, "Ranking Opportunities", len(accepted_items))
    rank_start = time.time()
    ranked_items = re.rank_batch(accepted_items)
    metrics.ranking_time = time.time() - rank_start

    # 7. Knowledge Base Database Persistence
    _notify("saving", 90.0, "Persisting Knowledge Base Records", len(ranked_items))
    db_start = time.time()
    saved_count = 0
    persistence_success = False
    persist_res = None
    sources_str = ",".join(getattr(search_plan, "sources_targeted", []))

    if not dry_run:
        # Create SearchHistory row first to satisfy FOREIGN KEY (run_id) REFERENCES SearchHistory(run_id)
        sql_init_hist = """
            INSERT INTO SearchHistory (
                run_id, triggered_at, completed_at, status, sources_run,
                items_collected, items_after_dedup, items_emailed, errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                triggered_at = excluded.triggered_at,
                completed_at = excluded.completed_at,
                status = excluded.status,
                sources_run = excluded.sources_run,
                items_collected = excluded.items_collected,
                items_after_dedup = excluded.items_after_dedup,
                items_emailed = excluded.items_emailed,
                errors = excluded.errors;
        """
        try:
            with db.transaction() as cursor:
                cursor.execute(
                    sql_init_hist,
                    (run_id, started_iso, started_iso, "running", sources_str, len(raw_items), len(ranked_items), 0, ""),
                )
        except Exception as e:
            logger.error(f"Failed to initialize SearchHistory record: {e}")

        persistence_error = None
        persist_res = None
        try:
            with db.transaction() as cursor:
                for opp in ranked_items:
                    opp.run_id = run_id
                for opp in quarantined_items:
                    opp.run_id = run_id
                persist_res = km.process_opportunity_batch(ranked_items + quarantined_items)
                saved_count = getattr(persist_res, "saved_count", int(persist_res))
            persistence_success = True

            try:
                km.opp_repo.update_lifecycle_states()
            except Exception as lce:
                logger.warning(f"Could not update lifecycle states: {lce}")

            # Phase 7: Process harvest notification events safely (never breaks harvest)
            if persist_res:
                try:
                    from src.intelligence.notification_engine import NotificationEngine
                    notif_engine = NotificationEngine(db_manager=db)
                    notif_engine.process_harvest_events(
                        new_items=getattr(persist_res, "new_items", []),
                        updated_items=getattr(persist_res, "updated_items", []),
                        reopened_items=getattr(persist_res, "reopened_items", []),
                    )
                except Exception as ne_err:
                    logger.error(f"[Pipeline] NotificationEngine enqueue failed (harvest preserved): {ne_err}")
        except Exception as hist_err:
            persistence_error = str(hist_err)
            logger.error(f"Database persistence failed: {hist_err}")
            persistence_success = False
            saved_count = 0
    else:
        persistence_success = True
        persistence_error = None

    metrics.db_update_time = time.time() - db_start

    new_count = getattr(persist_res, "new_count", 0) if persist_res else 0
    updated_count = getattr(persist_res, "updated_count", 0) if persist_res else 0
    unchanged_count = getattr(persist_res, "unchanged_count", 0) if persist_res else 0
    batch_dups = getattr(persist_res, "duplicate_count", 0) if persist_res else 0

    # 8. Notifications Phase — Strictly gated on successful database persistence and presence of new/updated items
    notify_start = time.time()
    email_sent = False
    email_error = None
    if not dry_run and send_email:
        if not persistence_success:
            logger.error("Email notification cancelled: Database persistence failed.")
            email_sent = False
            email_error = "Database persistence failed"
        elif not db.ping():
            logger.error("Email notification cancelled: Database connection unreachable.")
            email_sent = False
            email_error = "Database connection unreachable"
        elif new_count == 0 and updated_count == 0:
            logger.info("[Pipeline] Email notification skipped: 0 new or updated opportunities discovered.")
            email_sent = False
            email_error = None
        else:
            try:
                # Phase 7: Dispatch pending notifications via NotificationService
                try:
                    from src.services.notification_service import NotificationService
                    notif_service = NotificationService(db_manager=db)
                    notif_service.dispatch_pending()
                except Exception as nse:
                    logger.error(f"[Pipeline] Notification outbox dispatch error: {nse}")

                # Call legacy/digest email client for backward-compatibility with tests/reporting
                email_res = ec.send_daily_digest()
                email_sent = email_res.get("status") == "success"
                if not email_sent:
                    email_error = email_res.get("error") or "Email sending failed"
            except Exception as e:
                logger.error(f"Failed to send email notification: {e}")
                email_sent = False
                email_error = str(e)
    metrics.notification_time = time.time() - notify_start

    finished_time = time.time()
    finished_iso = datetime.now(timezone.utc).isoformat()
    duration_sec = round(finished_time - start_time, 2)
    metrics.total_time = duration_sec

    # Update completed SearchHistory record
    if not dry_run:
        sql_update_hist = """
            UPDATE SearchHistory SET
                completed_at = ?,
                status = ?,
                items_collected = ?,
                items_after_dedup = ?,
                items_emailed = ?,
                errors = ?
            WHERE run_id = ?;
        """
        history_status = "success" if persistence_success else "failed"
        history_err = "" if persistence_success else (persistence_error or "Persistence failed")
        try:
            with db.transaction() as cursor:
                cursor.execute(
                    sql_update_hist,
                    (finished_iso, history_status, len(raw_items), len(ranked_items), saved_count if email_sent else 0, history_err, run_id),
                )
        except Exception as e:
            logger.warning(f"Could not update pipeline run history in DB: {e}")

    # Structured Formatted Logging Block
    log_block = [
        "",
        "=================================================",
        f"Starting Pipeline Scan (Run ID: {run_id})",
        "=================================================",
    ]
    for collector, count in collectors_count.items():
        log_block.append(f"Collector: {collector}")
        log_block.append(f"Collected: {count}")
        log_block.append("")

    log_block.extend([
        f"Raw Items:\n{len(raw_items)}",
        "",
        f"Duplicates Removed:\n{duplicates_removed + batch_dups}",
        "",
        f"Quality Accepted:\n{len(accepted_items)}",
        "",
        f"Quality Rejected:\n{len(rejected_items)}",
        "",
        f"New Opportunities:\n{new_count}",
        "",
        f"Updated Opportunities:\n{updated_count}",
        "",
        f"Unchanged Opportunities:\n{unchanged_count}",
        "",
        f"Saved:\n{saved_count if not dry_run else 0}",
        "",
        f"Scan Complete ({duration_sec}s)",
        "=================================================",
    ])
    logger.info("\n".join(log_block))

    pipeline_status = "success" if persistence_success else "failed"
    pipeline_success = persistence_success

    return {
        "success": pipeline_success,
        "status": pipeline_status,
        "error": persistence_error,
        "email_error": email_error,
        "run_id": run_id,
        "started": started_iso,
        "finished": finished_iso,
        "duration_seconds": duration_sec,
        "collectors": collectors_count,
        "collector_status": collector_status,
        "raw_items": len(raw_items),
        "items_collected": len(raw_items),
        "items_processed": len(processed_items),
        "duplicates": duplicates_removed + batch_dups,
        "items_new": new_count,
        "items_updated": updated_count,
        "items_unchanged": unchanged_count,
        "accepted": len(accepted_items),
        "items_quality_accepted": len(accepted_items),
        "rejected": len(rejected_items),
        "items_quality_rejected": len(rejected_items),
        "items_ranked": len(ranked_items),
        "saved": saved_count if not dry_run else 0,
        "persistence_success": persistence_success,
        "email_sent": email_sent,
        "execution_time_sec": duration_sec,
        "quality_metrics": qe.metrics.to_dict(),
        "metrics": metrics.to_dict(),
    }


class PipelineRunner:
    """
    Executes the complete end-to-end CyberScout AI scan loop.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        search_planner: Optional[SearchPlanner] = None,
        collector_manager: Optional[CollectorManager] = None,
        processing_pipeline: Optional[ProcessingPipeline] = None,
        quality_engine: Optional[QualityEngine] = None,
        production_engine: Optional[ProductionEngine] = None,
        ranking_engine: Optional[RankingEngine] = None,
        knowledge_manager: Optional[KnowledgeManager] = None,
        email_client: Optional[EmailClient] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.search_planner = search_planner
        self.collector_manager = collector_manager
        self.processing_pipeline = processing_pipeline
        self.quality_engine = quality_engine
        self.production_engine = production_engine
        self.ranking_engine = ranking_engine
        self.knowledge_manager = knowledge_manager
        self.email_client = email_client

    def run_pipeline(self, dry_run: bool = False, send_email: bool = False) -> Dict[str, Any]:
        """Delegates directly to the single source of truth run_pipeline_once function."""
        return run_pipeline_once(
            dry_run=dry_run,
            send_email=send_email,
            db_manager=self.db_manager,
            search_planner=self.search_planner,
            collector_manager=self.collector_manager,
            processing_pipeline=self.processing_pipeline,
            quality_engine=self.quality_engine,
            production_engine=self.production_engine,
            ranking_engine=self.ranking_engine,
            knowledge_manager=self.knowledge_manager,
            email_client=self.email_client,
        )
