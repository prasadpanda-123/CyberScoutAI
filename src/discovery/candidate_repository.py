"""
Candidate Repository for CyberScout AI Discovery Layer.

Manages idempotent persistence of staged DiscoveredCandidate entities
in PostgreSQL, ensuring complete isolation from approved Opportunities.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.discovery.discovery_models import DiscoveredCandidate

logger = get_logger(__name__)

DDL_DISCOVERED_CANDIDATES = """
CREATE TABLE IF NOT EXISTS "DiscoveredCandidates" (
    id VARCHAR(64) PRIMARY KEY,
    url_hash VARCHAR(64) UNIQUE NOT NULL,
    canonical_url TEXT NOT NULL,
    original_url TEXT NOT NULL,
    title TEXT NOT NULL,
    snippet TEXT,
    search_query TEXT,
    search_provider VARCHAR(32) DEFAULT 'tavily',
    source_domain VARCHAR(255),
    platform_name VARCHAR(100),
    country_or_scope VARCHAR(100) DEFAULT 'Global',
    category VARCHAR(64) DEFAULT 'other',
    score FLOAT DEFAULT 0.0,
    pricing_verification_status VARCHAR(32) DEFAULT 'UNCERTAIN',
    is_free BOOLEAN,
    processing_status VARCHAR(32) DEFAULT 'discovered',
    extraction_status VARCHAR(32) DEFAULT 'pending',
    discovery_run_id VARCHAR(64),
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS "ix_discovered_candidates_url_hash" ON "DiscoveredCandidates" ("url_hash");
CREATE INDEX IF NOT EXISTS "ix_discovered_candidates_run_id" ON "DiscoveredCandidates" ("discovery_run_id");
CREATE INDEX IF NOT EXISTS "ix_discovered_candidates_extraction" ON "DiscoveredCandidates" ("extraction_status");
"""


class DiscoveredCandidateRepository:
    """
    DAO managing unverified opportunity candidates discovered from external search engines.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._table_ensured = False
        self._in_memory_cache: Dict[str, DiscoveredCandidate] = {}

    def ensure_table(self) -> bool:
        """Idempotently creates DiscoveredCandidates table and indexes if not present."""
        if self._table_ensured:
            return True

        if not self.db_manager.ping():
            logger.debug("Database unreachable; candidate repository using in-memory mode.")
            return False

        try:
            with self.db_manager.transaction() as cursor:
                # Execute DDL statements
                for statement in DDL_DISCOVERED_CANDIDATES.strip().split(";"):
                    stmt = statement.strip()
                    if stmt:
                        cursor.execute(stmt)
            self._table_ensured = True
            logger.debug("DiscoveredCandidates table schema initialized successfully.")
            return True
        except Exception as e:
            logger.warning(f"Could not verify DiscoveredCandidates schema: {e}")
            return False

    def is_url_in_approved_opportunities(self, url_hash: str) -> bool:
        """
        Checks if the candidate URL is already an active or archived record
        in the primary approved Opportunities table.
        """
        if not self.db_manager.ping():
            return False

        sql = 'SELECT 1 FROM "Opportunities" WHERE url_hash = ? LIMIT 1;'
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (url_hash,))
                row = cursor.fetchone()
                return bool(row)
            finally:
                cursor.close()
        except Exception as e:
            logger.debug(f"Error checking Opportunities for url_hash {url_hash}: {e}")
            return False

    def is_url_already_discovered(self, url_hash: str) -> bool:
        """Checks if URL hash exists in in-memory cache or DiscoveredCandidates table."""
        if url_hash in self._in_memory_cache:
            return True

        if not self.db_manager.ping():
            return False

        self.ensure_table()
        sql = 'SELECT 1 FROM "DiscoveredCandidates" WHERE url_hash = ? LIMIT 1;'
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (url_hash,))
                row = cursor.fetchone()
                return bool(row)
            finally:
                cursor.close()
        except Exception as e:
            logger.debug(f"Error checking DiscoveredCandidates for url_hash {url_hash}: {e}")
            return False

    def save_candidate(self, candidate: DiscoveredCandidate) -> Tuple[str, bool]:
        """
        Persists a single candidate.
        Returns:
            Tuple of (candidate_id, is_new).
        """
        results = self.save_candidates_batch([candidate])
        is_new = results[0] > 0
        return candidate.id, is_new

    def save_candidates_batch(self, candidates: List[DiscoveredCandidate]) -> Tuple[int, int]:
        """
        Persists a batch of DiscoveredCandidate records.
        Handles conflicts gracefully by updating existing candidate's discovery metadata.

        Returns:
            Tuple of (new_count, duplicate_count).
        """
        if not candidates:
            return 0, 0

        new_count = 0
        duplicate_count = 0

        # Always update in-memory cache for fast lookup during current run
        for cand in candidates:
            if cand.url_hash in self._in_memory_cache:
                duplicate_count += 1
            else:
                self._in_memory_cache[cand.url_hash] = cand
                new_count += 1

        if not self.db_manager.ping() or not self.ensure_table():
            # Return in-memory outcome if running offline/without DB
            return new_count, duplicate_count

        insert_sql = """
        INSERT INTO "DiscoveredCandidates" (
            id, url_hash, canonical_url, original_url, title, snippet,
            search_query, search_provider, source_domain, platform_name,
            country_or_scope, category, score, pricing_verification_status,
            is_free, processing_status, extraction_status, discovery_run_id,
            discovered_at, metadata
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?
        )
        ON CONFLICT (url_hash) DO UPDATE SET
            title = EXCLUDED.title,
            snippet = EXCLUDED.snippet,
            score = EXCLUDED.score,
            discovery_run_id = EXCLUDED.discovery_run_id;
        """

        db_new = 0
        db_dup = 0

        try:
            with self.db_manager.transaction() as cursor:
                for cand in candidates:
                    # Check if already present in DB
                    cursor.execute('SELECT id FROM "DiscoveredCandidates" WHERE url_hash = ?;', (cand.url_hash,))
                    row = cursor.fetchone()
                    if row:
                        db_dup += 1
                    else:
                        db_new += 1

                    meta_str = json.dumps(cand.metadata) if cand.metadata else "{}"
                    cursor.execute(
                        insert_sql,
                        (
                            cand.id,
                            cand.url_hash,
                            cand.canonical_url,
                            cand.original_url,
                            cand.title,
                            cand.snippet,
                            cand.search_query,
                            cand.search_provider,
                            cand.source_domain,
                            cand.platform_name,
                            cand.country_or_scope,
                            cand.category,
                            cand.score,
                            cand.pricing_verification_status,
                            cand.is_free,
                            cand.processing_status,
                            cand.extraction_status,
                            cand.discovery_run_id,
                            cand.discovered_at,
                            meta_str,
                        ),
                    )
            return db_new, db_dup
        except Exception as e:
            logger.error(f"Error persisting DiscoveredCandidates batch: {e}", exc_info=True)
            return new_count, duplicate_count

    def get_candidates_for_extraction(self, limit: int = 50) -> List[DiscoveredCandidate]:
        """
        Retrieves candidates awaiting content extraction (extraction_status = 'pending').
        Used by Phase C (Firecrawl).
        """
        if not self.db_manager.ping() or not self.ensure_table():
            return [c for c in self._in_memory_cache.values() if c.extraction_status == "pending"][:limit]

        sql = """
        SELECT * FROM "DiscoveredCandidates"
        WHERE extraction_status = 'pending' AND processing_status != 'security_rejected'
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
            logger.error(f"Error fetching candidates for extraction: {e}")
        return results

    def get_candidate_by_id(self, candidate_id: str) -> Optional[DiscoveredCandidate]:
        """Retrieves a single candidate by its primary ID."""
        for c in self._in_memory_cache.values():
            if c.id == candidate_id:
                return c

        if not self.db_manager.ping() or not self.ensure_table():
            return None

        sql = 'SELECT * FROM "DiscoveredCandidates" WHERE id = ? LIMIT 1;'
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (candidate_id,))
                r = cursor.fetchone()
                if not r:
                    return None
                raw_meta = r.get("metadata")
                meta_dict = json.loads(raw_meta) if isinstance(raw_meta, str) and raw_meta else {}
                return DiscoveredCandidate(
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
            finally:
                cursor.close()
        except Exception as e:
            logger.error(f"Error retrieving candidate by id '{candidate_id}': {e}")
            return None

    def get_candidate_by_url_hash(self, url_hash: str) -> Optional[DiscoveredCandidate]:
        """Retrieves a single candidate by its unique URL hash."""
        if url_hash in self._in_memory_cache:
            return self._in_memory_cache[url_hash]

        if not self.db_manager.ping() or not self.ensure_table():
            return None

        sql = 'SELECT * FROM "DiscoveredCandidates" WHERE url_hash = ? LIMIT 1;'
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (url_hash,))
                r = cursor.fetchone()
                if not r:
                    return None
                raw_meta = r.get("metadata")
                meta_dict = json.loads(raw_meta) if isinstance(raw_meta, str) and raw_meta else {}
                return DiscoveredCandidate(
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
            finally:
                cursor.close()
        except Exception as e:
            logger.error(f"Error retrieving candidate by url_hash '{url_hash}': {e}")
            return None

    def update_candidate_extraction(
        self,
        candidate_id: str,
        extraction_status: str,
        processing_status: Optional[str] = None,
        canonical_url: Optional[str] = None,
        title: Optional[str] = None,
        snippet: Optional[str] = None,
        metadata_updates: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Updates content extraction status and payload for an existing candidate in DiscoveredCandidates.
        Preserves candidate identity, original URL, and search query provenance.

        Args:
            candidate_id: UUID string of target candidate.
            extraction_status: New state ('completed', 'failed', 'skipped', 'in_progress').
            processing_status: Optional lifecycle update ('ready_for_verification', 'duplicate', 'security_rejected').
            canonical_url: Optional updated canonical destination after redirect verification.
            title: Optional refined title extracted from page H1/og:title.
            snippet: Optional refined short description extracted from page body.
            metadata_updates: Dictionary of extracted content fields to merge into metadata JSON.

        Returns:
            True if candidate was successfully updated, False otherwise.
        """
        # Update in-memory cache first
        for c in self._in_memory_cache.values():
            if c.id == candidate_id:
                c.extraction_status = extraction_status
                if processing_status:
                    c.processing_status = processing_status
                if canonical_url:
                    c.canonical_url = canonical_url
                if title:
                    c.title = title
                if snippet:
                    c.snippet = snippet
                if metadata_updates:
                    c.metadata.update(metadata_updates)
                break

        if not self.db_manager.ping() or not self.ensure_table():
            return True

        fetch_sql = 'SELECT metadata, canonical_url, title, snippet FROM "DiscoveredCandidates" WHERE id = ?;'
        update_sql = """
        UPDATE "DiscoveredCandidates" SET
            extraction_status = ?,
            processing_status = COALESCE(?, processing_status),
            canonical_url = COALESCE(?, canonical_url),
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
                    logger.warning(f"Candidate '{candidate_id}' not found in DiscoveredCandidates for extraction update.")
                    return False

                current_meta_str = row.get("metadata")
                current_meta: Dict[str, Any] = {}
                if isinstance(current_meta_str, str) and current_meta_str:
                    try:
                        current_meta = json.loads(current_meta_str)
                    except Exception:
                        current_meta = {}

                if metadata_updates:
                    current_meta.update(metadata_updates)

                new_meta_str = json.dumps(current_meta)

                cursor.execute(
                    update_sql,
                    (
                        extraction_status,
                        processing_status,
                        canonical_url,
                        title,
                        snippet,
                        new_meta_str,
                        candidate_id,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Failed to update candidate extraction for id '{candidate_id}': {e}", exc_info=True)
            return False


