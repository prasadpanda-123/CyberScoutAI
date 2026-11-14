"""
Free-Only Verification Repository for Staged Candidate Updates (Phase E).

Manages persistence of deterministic free-only verification decisions in the
DiscoveredCandidates staging table, ensuring complete isolation from production Opportunities.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.discovery_models import DiscoveredCandidate
from src.discovery.free_only_models import FreeOnlyEvaluation

logger = get_logger(__name__)


class FreeOnlyRepository:
    """
    DAO managing persistence and retrieval of candidates undergoing Phase E free-only verification.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        candidate_repo: Optional[DiscoveredCandidateRepository] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.candidate_repo = candidate_repo or DiscoveredCandidateRepository(db_manager=self.db_manager)
        self._schema_verified = False

    def ensure_free_only_schema(self) -> bool:
        """Idempotently ensures DiscoveredCandidates has free_only_decision columns."""
        if self._schema_verified:
            return True

        if not self.db_manager.ping():
            return False

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    'ALTER TABLE "DiscoveredCandidates" ADD COLUMN IF NOT EXISTS free_only_decision VARCHAR(32) DEFAULT \'QUARANTINED\';'
                )
                cursor.execute(
                    'ALTER TABLE "DiscoveredCandidates" ADD COLUMN IF NOT EXISTS verification_reason TEXT;'
                )
            self._schema_verified = True
            return True
        except Exception as e:
            logger.debug(f"Free-only schema check notice: {e}")
            self._schema_verified = True
            return True

    def get_candidates_for_verification(self, limit: int = 25) -> List[DiscoveredCandidate]:
        """
        Retrieves candidates that have completed AI classification and await free-only verification.

        Criteria:
        1. processing_status = 'classified' or classification_status = 'completed'
        2. free_only_decision is not set (or is 'PENDING')
        3. processing_status != 'security_rejected' and != 'duplicate'
        """
        if not self.db_manager.ping() or not self.candidate_repo.ensure_table():
            # In-memory mode fallback
            candidates: List[DiscoveredCandidate] = []
            for c in self.candidate_repo._in_memory_cache.values():
                is_classified = (
                    c.processing_status == "classified"
                    or c.metadata.get("classification_status") == "completed"
                )
                if is_classified and c.processing_status not in ("security_rejected", "duplicate"):
                    decision = c.metadata.get("free_only_decision")
                    if not decision or decision == "PENDING":
                        candidates.append(c)
                        if len(candidates) >= limit:
                            break
            return candidates

        self.ensure_free_only_schema()

        sql = """
        SELECT * FROM "DiscoveredCandidates"
        WHERE (processing_status = 'classified' OR classification_status = 'completed')
          AND processing_status NOT IN ('security_rejected', 'duplicate')
          AND (free_only_decision IS NULL OR free_only_decision = 'PENDING')
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
            logger.error(f"[FreeOnlyRepository] Error fetching candidates for verification: {e}")
        return results

    def update_candidate_verification(
        self,
        candidate_id: str,
        evaluation: FreeOnlyEvaluation,
    ) -> bool:
        """
        Persists deterministic Free-Only evaluation outcome into DiscoveredCandidates staging table.
        Does NOT insert or modify records in the production Opportunities table.
        """
        new_processing_status = "quarantined"
        if evaluation.decision.value == "APPROVED":
            new_processing_status = "verified"
        elif evaluation.decision.value == "REJECTED":
            new_processing_status = "rejected"

        # Update in-memory cache first
        for c in self.candidate_repo._in_memory_cache.values():
            if c.id == candidate_id:
                c.pricing_verification_status = evaluation.pricing_verification_status.value
                c.is_free = evaluation.is_free
                c.processing_status = new_processing_status
                c.metadata["free_only_verification"] = evaluation.to_dict()
                c.metadata["free_only_decision"] = evaluation.decision.value
                c.metadata["verification_reason"] = evaluation.verification_reason
                break

        if not self.db_manager.ping() or not self.candidate_repo.ensure_table():
            return True

        self.ensure_free_only_schema()

        fetch_sql = 'SELECT metadata FROM "DiscoveredCandidates" WHERE id = ?;'
        update_sql = """
        UPDATE "DiscoveredCandidates" SET
            pricing_verification_status = ?,
            is_free = ?,
            processing_status = ?,
            free_only_decision = ?,
            verification_reason = ?,
            metadata = ?
        WHERE id = ?;
        """

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(fetch_sql, (candidate_id,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"[FreeOnlyRepository] Candidate '{candidate_id}' not found for verification update.")
                    return False

                current_meta_str = row.get("metadata")
                current_meta: Dict[str, Any] = {}
                if isinstance(current_meta_str, str) and current_meta_str:
                    try:
                        current_meta = json.loads(current_meta_str)
                    except Exception:
                        current_meta = {}

                current_meta["free_only_verification"] = evaluation.to_dict()
                current_meta["free_only_decision"] = evaluation.decision.value
                current_meta["verification_reason"] = evaluation.verification_reason
                new_meta_str = json.dumps(current_meta)

                cursor.execute(
                    update_sql,
                    (
                        evaluation.pricing_verification_status.value,
                        evaluation.is_free,
                        new_processing_status,
                        evaluation.decision.value,
                        evaluation.verification_reason,
                        new_meta_str,
                        candidate_id,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"[FreeOnlyRepository] Failed to update candidate verification '{candidate_id}': {e}", exc_info=True)
            return False

