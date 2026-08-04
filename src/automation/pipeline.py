"""
Automated Pipeline Runner for CyberScout AI.
"""

import time
from typing import Any, Dict, List, Optional
import uuid

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.knowledge_manager import KnowledgeManager
from src.collectors.manager import CollectorManager
from src.intelligence.search_planner import SearchPlanner
from src.intelligence.ranking_engine import RankingEngine
from src.models.opportunity import Opportunity
from src.processors.pipeline import ProcessingPipeline
from src.notifier.email_client import EmailClient
from src.automation.metrics import RunMetrics

logger = get_logger(__name__)


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
        ranking_engine: Optional[RankingEngine] = None,
        knowledge_manager: Optional[KnowledgeManager] = None,
        email_client: Optional[EmailClient] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.search_planner = search_planner or SearchPlanner()
        self.collector_manager = collector_manager or CollectorManager()
        self.processing_pipeline = processing_pipeline or ProcessingPipeline()
        self.ranking_engine = ranking_engine or RankingEngine()
        self.knowledge_manager = knowledge_manager or KnowledgeManager(db_manager=self.db_manager)
        self.email_client = email_client or EmailClient(db_manager=self.db_manager)

    def run_pipeline(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Runs one complete scan loop.

        Args:
            dry_run: If True, bypasses database writes and email sending.

        Returns:
            Dictionary containing metrics and stats summaries.
        """
        run_id = f"run-{uuid.uuid4()}"
        metrics = RunMetrics(run_id=run_id)
        start_time = time.time()
        logger.info(f"Starting pipeline runner execution. Run ID: {run_id} (Dry Run: {dry_run})")

        # 1. Search Planning Phase
        plan_start = time.time()
        search_plan = self.search_planner.create_search_plan()
        metrics.planning_time = time.time() - plan_start
        logger.info(f"Pipeline: Planning complete. Time: {metrics.planning_time:.4f}s")

        # 2. Collection Phase
        collect_start = time.time()
        collector_results = self.collector_manager.execute_plan(search_plan)
        metrics.collection_time = time.time() - collect_start

        # Extract items and coerce dicts → Opportunity models
        raw_items = []
        for res in collector_results:
            if res.items:
                for item in res.items:
                    if isinstance(item, Opportunity):
                        raw_items.append(item)
                    elif isinstance(item, dict):
                        try:
                            opp = Opportunity(
                                title=item.get("title", "Untitled"),
                                url=item.get("url", item.get("link", "")),
                                source_id=item.get("source_id", res.source_id),
                                description=item.get("description", item.get("summary", None)),
                                category=item.get("category", "other"),
                                published_date=item.get("published", item.get("published_date", None)),
                                raw_data=item,
                            )
                            raw_items.append(opp)
                        except Exception as conv_err:
                            logger.debug(f"Skipping unconvertible item from {res.source_id}: {conv_err}")
        logger.info(f"Pipeline: Collection complete. Collected {len(raw_items)} items. Time: {metrics.collection_time:.4f}s")

        # 3. Processing Phase
        process_start = time.time()
        processed_items = self.processing_pipeline.process_batch(raw_items)
        metrics.processing_time = time.time() - process_start
        logger.info(f"Pipeline: Processing complete. Processed {len(processed_items)} items. Time: {metrics.processing_time:.4f}s")

        # 4. Ranking Phase
        rank_start = time.time()
        ranked_items = self.ranking_engine.rank_batch(processed_items)
        metrics.ranking_time = time.time() - rank_start
        logger.info(f"Pipeline: Ranking complete. Ranked {len(ranked_items)} items. Time: {metrics.ranking_time:.4f}s")

        # 5. Knowledge Base Updates
        db_start = time.time()
        if not dry_run:
            for opp in ranked_items:
                self.knowledge_manager.process_opportunity_state(opp)
        metrics.db_update_time = time.time() - db_start
        logger.info(f"Pipeline: Knowledge Base update complete. Time: {metrics.db_update_time:.4f}s")

        # 6. Notifications Phase
        notify_start = time.time()
        email_sent = False
        if not dry_run:
            email_res = self.email_client.send_daily_digest()
            email_sent = email_res.get("status") == "success"
        metrics.notification_time = time.time() - notify_start
        logger.info(f"Pipeline: Notification complete. Sent: {email_sent}. Time: {metrics.notification_time:.4f}s")

        metrics.total_time = time.time() - start_time
        logger.info(f"Pipeline run completed in {metrics.total_time:.2f} seconds.")

        # Record run history to DB if not dry run
        if not dry_run:
            self._record_run_history(run_id, search_plan, raw_items, ranked_items, email_sent, metrics)

        return {
            "status": "success",
            "run_id": run_id,
            "providers_attempted": getattr(getattr(self.collector_manager, "metrics", None), "providers_attempted", 0),
            "providers_succeeded": getattr(getattr(self.collector_manager, "metrics", None), "providers_succeeded", 0),
            "providers_failed": getattr(getattr(self.collector_manager, "metrics", None), "providers_failed", 0),
            "items_collected": len(raw_items),
            "items_processed": len(processed_items),
            "items_ranked": len(ranked_items),
            "email_sent": email_sent,
            "execution_time_sec": round(metrics.total_time, 2),
            "metrics": metrics.to_dict(),
        }

    def _record_run_history(
        self,
        run_id: str,
        plan: Any,
        raw_items: List[Any],
        ranked_items: List[Any],
        email_sent: bool,
        metrics: RunMetrics,
    ) -> None:
        """Saves run execution log inside SearchHistory database table."""
        sql = """
            INSERT INTO SearchHistory (
                run_id, triggered_at, completed_at, status, sources_run,
                items_collected, items_after_dedup, items_emailed, errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        sources_str = ",".join(getattr(plan, "sources_targeted", []))
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (
                        run_id,
                        now,
                        now,
                        "success",
                        sources_str,
                        len(raw_items),
                        len(ranked_items),
                        len(ranked_items) if email_sent else 0,
                        "",
                    ),
                )
        except Exception as e:
            logger.warning(f"Could not record pipeline run history to DB: {e}")
