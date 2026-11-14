"""
Classification Repository for Staged Candidate Persistence (Phase D).

Manages persistence of AI classification outcomes in the DiscoveredCandidates staging
table, ensuring complete isolation from the production Opportunities table.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.classification_models import ClassificationResult
from src.discovery.discovery_models import DiscoveredCandidate

logger = get_logger(__name__)


class ClassificationRepository:
    """
    DAO managing persistence and retrieval of candidates undergoing AI classification.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        candidate_repo: Optional[DiscoveredCandidateRepository] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.candidate_repo = candidate_repo or DiscoveredCandidateRepository(db_manager=self.db_manager)
        self._schema_verified = False

    def ensure_classification_schema(self) -> bool:
        """Ensures DiscoveredCandidates has classification-related columns."""
        if self._schema_verified:
            return True

        if not self.db_manager.ping():
            return False

        try:
            with self.db_manager.transaction() as cursor:
                # Add classification_status column idempotently if PostgreSQL
                cursor.execute(
                    'ALTER TABLE "DiscoveredCandidates" ADD COLUMN IF NOT EXISTS classification_status VARCHAR(32) DEFAULT \'pending\';'
                )
            self._schema_verified = True
            return True
        except Exception as e:
            logger.debug(f"Classification schema check notice (table might be managed or sqlite in tests): {e}")
            self._schema_verified = True
            return True

    def get_candidates_for_classification(self, limit: int = 25) -> List[DiscoveredCandidate]:
        """
        Retrieves staged candidates ready for AI classification.
        
        Selection criteria:
        1. extraction_status = 'completed' (Firecrawl extracted page content)
        2. processing_status != 'security_rejected' and processing_status != 'duplicate'
        3. classification_status is pending or not yet classified.
        """
        if not self.db_manager.ping() or not self.candidate_repo.ensure_table():
            # In-memory fallback
            candidates: List[DiscoveredCandidate] = []
            for c in self.candidate_repo._in_memory_cache.values():
                if c.extraction_status == "completed" and c.processing_status not in ("security_rejected", "duplicate"):
                    classification_status = c.metadata.get("classification_status") or "pending"
                    if classification_status == "pending":
                        candidates.append(c)
                        if len(candidates) >= limit:
                            break
            return candidates

        self.ensure_classification_schema()

        sql = """
        SELECT * FROM "DiscoveredCandidates"
        WHERE extraction_status = 'completed'
          AND processing_status NOT IN ('security_rejected', 'duplicate')
          AND (classification_status IS NULL OR classification_status = 'pending')
        ORDER BY discovered_at ASC
        LIMIT ?;
        """
        results: List[DiscoveredCandidate] = []
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (limit,))
                rows = cursor.fetchall() or []
                for r in rows:
                    raw_meta = r.get("metadata")
                    meta_dict = json.loads(raw_meta) if isinstance(raw_meta, str) and raw_meta else {}
                    cand = DiscoveredCandidate(
                        id=r["id"],
                        discovery_run_id=r["discovery_run_id"],
                        search_query=r["search_query"],
                        search_provider=r["search_provider"],
                        original_url=r["original_url"],
                        canonical_url=r["canonical_url"],
                        url_hash=r["url_hash"],
                        title=r["title"],
                        snippet=r["snippet"] or "",
                        source_domain=r["source_domain"] or "",
                        platform_name=r.get("platform_name"),
                        country_or_scope=r.get("country_or_scope", "Global"),
                        category=r.get("category", "other"),
                        score=float(r.get("score") or 0.0),
                        pricing_verification_status=r.get("pricing_verification_status", "UNCERTAIN"),
                        is_free=r.get("is_free"),
                        processing_status=r.get("processing_status", "discovered"),
                        extraction_status=r.get("extraction_status", "pending"),
                        discovered_at=str(r.get("discovered_at")),
                        metadata=meta_dict,
                    )
                    results.append(cand)
            finally:
                cursor.close()
        except Exception as e:
            logger.error(f"[ClassificationRepository] Error fetching candidates for classification: {e}")
        return results

    def update_candidate_classification(
        self,
        candidate_id: str,
        result: ClassificationResult,
    ) -> bool:
        """
        Persists validated AI classification outcome into DiscoveredCandidates staging table.
        Does NOT promote to production Opportunities table.
        """
        # Update in-memory cache first
        for c in self.candidate_repo._in_memory_cache.values():
            if c.id == candidate_id:
                c.category = result.category
                c.title = result.title or c.title
                c.snippet = result.description or c.snippet
                c.metadata["classification"] = result.to_dict()
                c.metadata["classification_status"] = "completed"
                c.processing_status = "classified"
                break

        if not self.db_manager.ping() or not self.candidate_repo.ensure_table():
            return True

        self.ensure_classification_schema()

        fetch_sql = 'SELECT metadata, title, snippet FROM "DiscoveredCandidates" WHERE id = ?;'
        update_sql = """
        UPDATE "DiscoveredCandidates" SET
            category = ?,
            classification_status = 'completed',
            processing_status = 'classified',
            title = COALESCE(?, title),
            snippet = COALESCE(?, snippet),
            metadata = ?
        WHERE id = ?;
        """

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(fetch_sql, (candidate_id,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"[ClassificationRepository] Candidate '{candidate_id}' not found for classification update.")
                    return False

                current_meta_str = row.get("metadata")
                current_meta: Dict[str, Any] = {}
                if isinstance(current_meta_str, str) and current_meta_str:
                    try:
                        current_meta = json.loads(current_meta_str)
                    except Exception:
                        current_meta = {}

                current_meta["classification"] = result.to_dict()
                current_meta["classification_status"] = "completed"
                new_meta_str = json.dumps(current_meta)

                cursor.execute(
                    update_sql,
                    (
                        result.category,
                        result.title,
                        result.description,
                        new_meta_str,
                        candidate_id,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"[ClassificationRepository] Failed to update candidate classification '{candidate_id}': {e}", exc_info=True)
            return False

    def mark_classification_failed(
        self,
        candidate_id: str,
        error_reason: str,
        provider_errors: Optional[List[str]] = None,
    ) -> bool:
        """
        Marks candidate classification as failed or pending retry in DiscoveredCandidates.
        Preserves candidate staging record for subsequent processing runs.
        """
        for c in self.candidate_repo._in_memory_cache.values():
            if c.id == candidate_id:
                c.metadata["classification_status"] = "failed"
                c.metadata["classification_error"] = error_reason
                c.metadata["classification_provider_errors"] = provider_errors or []
                break

        if not self.db_manager.ping() or not self.candidate_repo.ensure_table():
            return True

        self.ensure_classification_schema()

        fetch_sql = 'SELECT metadata FROM "DiscoveredCandidates" WHERE id = ?;'
        update_sql = """
        UPDATE "DiscoveredCandidates" SET
            classification_status = 'failed',
            metadata = ?
        WHERE id = ?;
        """

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(fetch_sql, (candidate_id,))
                row = cursor.fetchone()
                if not row:
                    return False

                current_meta_str = row.get("metadata")
                current_meta: Dict[str, Any] = {}
                if isinstance(current_meta_str, str) and current_meta_str:
                    try:
                        current_meta = json.loads(current_meta_str)
                    except Exception:
                        current_meta = {}

                current_meta["classification_status"] = "failed"
                current_meta["classification_error"] = error_reason
                current_meta["classification_provider_errors"] = provider_errors or []
                new_meta_str = json.dumps(current_meta)

                cursor.execute(update_sql, (new_meta_str, candidate_id))
            return True
        except Exception as e:
            logger.error(f"[ClassificationRepository] Failed to mark candidate '{candidate_id}' as failed: {e}")
            return False

