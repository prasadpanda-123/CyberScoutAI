"""
Opportunity Repository for CyberScout AI.

Handles database CRUD, upserts, duplicate management, and lifecycle status
updates for Opportunity objects in PostgreSQL.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.interfaces import IOpportunityRepository
from src.models.enums import Status
from src.models.opportunity import Opportunity
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)


class OpportunityRepository(BaseRepository[Opportunity], IOpportunityRepository):
    """
    DAO for managing Opportunity records in PostgreSQL.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        super().__init__(db_manager=db_manager)

    @property
    def table_name(self) -> str:
        return "Opportunities"

    @property
    def primary_key(self) -> str:
        return "id"

    def _entity_to_dict(self, opp: Opportunity) -> Dict[str, Any]:
        url_hash = opp.generate_url_hash()
        return {
            "id": opp.id,
            "title": opp.title,
            "description": opp.description,
            "url": opp.url,
            "url_hash": url_hash,
            "source_id": opp.source_id,
            "category": opp.category,
            "provider": opp.provider,
            "company": opp.company,
            "location": opp.location,
            "remote": bool(opp.remote),
            "paid": bool(opp.paid) if opp.paid is not None else None,
            "certificate": bool(opp.certificate),
            "price_raw": opp.price_raw,
            "price_normalized": opp.price_normalized,
            "currency": opp.currency,
            "deadline": opp.deadline,
            "published_date": opp.published_date,
            "discovered_date": opp.discovered_date,
            "duration": opp.duration,
            "difficulty": opp.difficulty,
            "tags": json.dumps(opp.tags),
            "beginner_friendly": bool(opp.beginner_friendly) if opp.beginner_friendly is not None else None,
            "score": opp.score,
            "score_breakdown": json.dumps(opp.score_breakdown),
            "confidence_score": opp.confidence_score,
            "quality_score": opp.quality_score,
            "is_rejected": bool(opp.is_rejected),
            "rejection_reason": opp.rejection_reason,
            "quality_flags": opp.quality_flags,
            "topic_score": opp.topic_score,
            "keyword_score": opp.keyword_score,
            "spam_score": opp.spam_score,
            "freshness_score": opp.freshness_score,
            "provider_score": opp.provider_score,
            "link_status": opp.link_status,
            "verification_status": opp.verification_status,
            "last_verified": opp.last_verified,
            "expired": opp.expired,
            "archived": opp.archived,
            "status": opp.status,
            "duplicate_of_id": opp.duplicate_of_id,
            "run_id": opp.run_id,
            "raw_data": json.dumps(opp.raw_data),
            "last_seen": opp.last_seen,
        }

    def _row_to_entity(self, row: Any) -> Opportunity:
        def _get_field(key: str, default: Any = None) -> Any:
            try:
                val = row[key]
                return val if val is not None else default
            except (IndexError, KeyError):
                return default

        def _parse_json(val: Any, default: Any) -> Any:
            if val is None:
                return default
            if isinstance(val, (dict, list)):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return default
            return default

        tags = _parse_json(_get_field("tags"), [])
        score_breakdown = _parse_json(_get_field("score_breakdown"), {})
        raw_data = _parse_json(_get_field("raw_data"), {})

        return Opportunity(
            id=row["id"],
            title=row["title"],
            description=_get_field("description"),
            url=row["url"],
            source_id=row["source_id"],
            category=row["category"],
            provider=_get_field("provider"),
            company=_get_field("company"),
            location=_get_field("location"),
            remote=bool(_get_field("remote", False)),
            paid=bool(_get_field("paid")) if _get_field("paid") is not None else None,
            certificate=bool(_get_field("certificate", False)),
            price_raw=_get_field("price_raw"),
            price_normalized=_get_field("price_normalized"),
            currency=_get_field("currency"),
            deadline=_get_field("deadline"),
            published_date=_get_field("published_date"),
            discovered_date=row["discovered_date"],
            duration=_get_field("duration"),
            difficulty=_get_field("difficulty", "unknown"),
            tags=tags,
            beginner_friendly=bool(_get_field("beginner_friendly")) if _get_field("beginner_friendly") is not None else None,
            score=_get_field("score", 0),
            score_breakdown=score_breakdown,
            confidence_score=float(_get_field("confidence_score", 0.0)),
            quality_score=float(_get_field("quality_score", 0.0)),
            is_rejected=bool(_get_field("is_rejected", False)),
            rejection_reason=_get_field("rejection_reason", ""),
            quality_flags=_get_field("quality_flags", ""),
            topic_score=float(_get_field("topic_score", 0.0)),
            keyword_score=float(_get_field("keyword_score", 0.0)),
            spam_score=float(_get_field("spam_score", 0.0)),
            freshness_score=float(_get_field("freshness_score", 100.0)),
            provider_score=float(_get_field("provider_score", 100.0)),
            link_status=_get_field("link_status", "valid"),
            verification_status=_get_field("verification_status", "verified"),
            last_verified=_get_field("last_verified"),
            expired=int(_get_field("expired", 0)),
            archived=int(_get_field("archived", 0)),
            status=_get_field("status", "active"),
            duplicate_of_id=_get_field("duplicate_of_id"),
            run_id=_get_field("run_id"),
            raw_data=raw_data,
            last_seen=_get_field("last_seen"),
        )

    def upsert(self, opp: Opportunity) -> str:
        """Inserts or updates an Opportunity based on ID or url_hash."""
        data = self._entity_to_dict(opp)
        sql = """
        INSERT INTO Opportunities (
            id, title, description, url, url_hash, source_id, category,
            provider, company, location, remote, paid, certificate,
            price_raw, price_normalized, currency, deadline, published_date,
            discovered_date, duration, difficulty, tags, beginner_friendly,
            score, score_breakdown,
            confidence_score, quality_score, is_rejected, rejection_reason,
            quality_flags, topic_score, keyword_score, spam_score,
            status, duplicate_of_id, run_id,
            raw_data, last_seen
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            category = excluded.category,
            provider = excluded.provider,
            company = excluded.company,
            location = excluded.location,
            deadline = excluded.deadline,
            published_date = excluded.published_date,
            score = excluded.score,
            score_breakdown = excluded.score_breakdown,
            confidence_score = excluded.confidence_score,
            quality_score = excluded.quality_score,
            is_rejected = excluded.is_rejected,
            rejection_reason = excluded.rejection_reason,
            quality_flags = excluded.quality_flags,
            topic_score = excluded.topic_score,
            keyword_score = excluded.keyword_score,
            spam_score = excluded.spam_score,
            status = excluded.status,
            duplicate_of_id = excluded.duplicate_of_id,
            last_seen = excluded.last_seen;
        """
        values = (
            data["id"], data["title"], data["description"], data["url"], data["url_hash"],
            data["source_id"], data["category"], data["provider"], data["company"], data["location"],
            data["remote"], data["paid"], data["certificate"], data["price_raw"], data["price_normalized"],
            data["currency"], data["deadline"], data["published_date"], data["discovered_date"], data["duration"],
            data["difficulty"], data["tags"], data["beginner_friendly"], data["score"], data["score_breakdown"],
            data["confidence_score"], data["quality_score"], data["is_rejected"], data["rejection_reason"],
            data["quality_flags"], data["topic_score"], data["keyword_score"], data["spam_score"],
            data["status"], data["duplicate_of_id"], data["run_id"], data["raw_data"], data["last_seen"]
        )

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
            return opp.id
        except Exception as e:
            raise RepositoryError(f"Failed to upsert Opportunity '{opp.id}': {e}", original_exception=e)

    def upsert_batch(self, opps: List[Opportunity]) -> int:
        """Executes a batch upsert for a list of Opportunity objects using executemany."""
        if not opps:
            return 0

        sql = """
        INSERT INTO Opportunities (
            id, title, description, url, url_hash,
            source_id, category, provider, company, location,
            remote, paid, certificate, price_raw, price_normalized,
            currency, deadline, published_date, discovered_date, duration,
            difficulty, tags, beginner_friendly, score, score_breakdown,
            confidence_score, quality_score, is_rejected, rejection_reason,
            quality_flags, topic_score, keyword_score, spam_score,
            status, duplicate_of_id, run_id, raw_data, last_seen
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            category = excluded.category,
            provider = excluded.provider,
            company = excluded.company,
            location = excluded.location,
            deadline = excluded.deadline,
            published_date = excluded.published_date,
            score = excluded.score,
            score_breakdown = excluded.score_breakdown,
            confidence_score = excluded.confidence_score,
            quality_score = excluded.quality_score,
            is_rejected = excluded.is_rejected,
            rejection_reason = excluded.rejection_reason,
            quality_flags = excluded.quality_flags,
            topic_score = excluded.topic_score,
            keyword_score = excluded.keyword_score,
            spam_score = excluded.spam_score,
            status = excluded.status,
            duplicate_of_id = excluded.duplicate_of_id,
            last_seen = excluded.last_seen;
        """
        seq = []
        for opp in opps:
            data = self._entity_to_dict(opp)
            seq.append((
                data["id"], data["title"], data["description"], data["url"], data["url_hash"],
                data["source_id"], data["category"], data["provider"], data["company"], data["location"],
                data["remote"], data["paid"], data["certificate"], data["price_raw"], data["price_normalized"],
                data["currency"], data["deadline"], data["published_date"], data["discovered_date"], data["duration"],
                data["difficulty"], data["tags"], data["beginner_friendly"], data["score"], data["score_breakdown"],
                data["confidence_score"], data["quality_score"], data["is_rejected"], data["rejection_reason"],
                data["quality_flags"], data["topic_score"], data["keyword_score"], data["spam_score"],
                data["status"], data["duplicate_of_id"], data["run_id"], data["raw_data"], data["last_seen"]
            ))

        try:
            with self.db_manager.transaction() as cursor:
                cursor.executemany(sql, seq)
            return len(opps)
        except Exception as e:
            raise RepositoryError(f"Failed batch upsert for {len(opps)} opportunities: {e}", original_exception=e)

    def get_by_id(self, opp_id: str) -> Optional[Opportunity]:
        return self.read_by_id(opp_id)

    def get_by_url_hash(self, url_hash: str) -> Optional[Opportunity]:
        results = self.search(where_clause="url_hash = ?", params=(url_hash,), limit=1)
        return results[0] if results else None

    def get_active_opportunities(
        self, limit: int = 50, category: Optional[str] = None
    ) -> List[Opportunity]:
        return self.get_paginated_opportunities(limit=limit, offset=0, category=category)

    def _build_active_where(
        self,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        deadline_filter: Optional[str] = None,
    ) -> tuple[str, tuple[Any, ...]]:
        where_clause = "status = ? AND (is_rejected IS NOT TRUE) AND (expired = 0 OR expired IS NULL) AND (archived = 0 OR archived IS NULL)"
        params: List[Any] = [Status.ACTIVE.value]

        if category and category.lower() != "all":
            where_clause += " AND LOWER(category) = LOWER(?)"
            params.append(category.strip())

        if search_query and search_query.strip():
            q_term = f"%{search_query.strip().lower()}%"
            where_clause += " AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(company) LIKE ? OR LOWER(provider) LIKE ?)"
            params.extend([q_term, q_term, q_term, q_term])

        if deadline_filter:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if deadline_filter == "closing_soon":
                from datetime import timedelta
                soon_str = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d")
                where_clause += " AND (deadline IS NOT NULL AND deadline != '' AND deadline >= ? AND deadline <= ?)"
                params.extend([today_str, soon_str])
            elif deadline_filter == "no_deadline":
                where_clause += " AND (deadline IS NULL OR deadline = '')"
            elif deadline_filter == "passed":
                where_clause += " AND (deadline IS NOT NULL AND deadline != '' AND deadline < ?)"
                params.append(today_str)
            elif deadline_filter == "active":
                where_clause += " AND (deadline IS NULL OR deadline = '' OR deadline >= ?)"
                params.append(today_str)

        return where_clause, tuple(params)

    def count_paginated_opportunities(
        self,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        deadline_filter: Optional[str] = None,
    ) -> int:
        """Counts active opportunities matching category, search, and deadline filters."""
        where_clause, params = self._build_active_where(
            category=category,
            search_query=search_query,
            deadline_filter=deadline_filter,
        )
        return self.count(where_clause=where_clause, params=params)

    def get_paginated_opportunities(
        self,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        deadline_filter: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> List[Opportunity]:
        """Queries active opportunities using PostgreSQL server-side pagination with flexible sorting."""
        where_clause, params = self._build_active_where(
            category=category,
            search_query=search_query,
            deadline_filter=deadline_filter,
        )

        order_by = "score DESC, discovered_date DESC"
        if sort_by == "newest":
            order_by = "discovered_date DESC, score DESC"
        elif sort_by == "deadline_soonest":
            order_by = "CASE WHEN deadline IS NOT NULL AND deadline != '' THEN deadline ELSE '9999-12-31' END ASC, score DESC"
        elif sort_by == "score" or sort_by == "relevance":
            order_by = "score DESC, discovered_date DESC"

        return self.search(
            where_clause=where_clause,
            params=params,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )


    def get_rejected_opportunities(
        self, limit: int = 100
    ) -> List[Opportunity]:
        """Retrieves rejected opportunities for quality reporting."""
        return self.search(
            where_clause="is_rejected IS TRUE OR is_rejected = 1",
            order_by="discovered_date DESC",
            limit=limit,
        )

    def get_quality_stats(self) -> Dict[str, Any]:
        """Computes quality intelligence statistics from the database."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            stats = {}
            cursor.execute("SELECT COUNT(*) FROM Opportunities WHERE is_rejected IS NOT TRUE;")
            row = cursor.fetchone()
            stats["accepted_count"] = row[0] if row else 0

            cursor.execute("SELECT COUNT(*) FROM Opportunities WHERE is_rejected IS TRUE;")
            row = cursor.fetchone()
            stats["rejected_count"] = row[0] if row else 0

            cursor.execute("SELECT AVG(confidence_score) FROM Opportunities WHERE (is_rejected IS NOT TRUE) AND confidence_score > 0;")
            row = cursor.fetchone()
            stats["avg_confidence"] = round(float(row[0]) if row and row[0] is not None else 0.0, 1)

            cursor.execute("SELECT AVG(quality_score) FROM Opportunities WHERE (is_rejected IS NOT TRUE) AND quality_score > 0;")
            row = cursor.fetchone()
            stats["avg_quality"] = round(float(row[0]) if row and row[0] is not None else 0.0, 1)

            cursor.execute("SELECT rejection_reason, COUNT(*) FROM Opportunities WHERE is_rejected IS TRUE GROUP BY rejection_reason ORDER BY COUNT(*) DESC LIMIT 10;")
            rows = cursor.fetchall()
            stats["top_rejection_reasons"] = {r[0]: r[1] for r in rows} if rows else {}

            return stats
        finally:
            cursor.close()

    def update_status(self, opp_id: str, new_status: str) -> None:
        sql = "UPDATE Opportunities SET status = ? WHERE id = ?;"
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (new_status, opp_id))

    def mark_as_duplicate(self, opp_id: str, canonical_id: str) -> None:
        sql = "UPDATE Opportunities SET status = ?, duplicate_of_id = ? WHERE id = ?;"
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (Status.DUPLICATE.value, canonical_id, opp_id))

    def delete_old_records(self, days: int = 30) -> int:
        """Deletes opportunities discovered more than specified days ago."""
        from datetime import datetime, timedelta, timezone
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        sql = "DELETE FROM Opportunities WHERE discovered_date < ?;"
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (cutoff_date,))
            return cursor.rowcount if hasattr(cursor, "rowcount") and cursor.rowcount is not None else 0

    def save_opportunity_with_deduplication(self, opp: Opportunity) -> Tuple[str, bool]:
        """
        Pre-insert duplicate detection & field merging based on canonical URL.

        Returns:
            Tuple of (opportunity_id, is_duplicate_boolean).
        """
        url_hash = opp.generate_url_hash()
        existing = self.get_by_url_hash(url_hash)

        if existing:
            # Merge missing / higher-quality fields into existing survivor
            if not existing.deadline and opp.deadline:
                existing.deadline = opp.deadline
            elif existing.deadline and opp.deadline and opp.deadline != existing.deadline:
                existing.deadline = opp.deadline
            if not existing.published_date and opp.published_date:
                existing.published_date = opp.published_date
            if (not existing.description or len(opp.description or "") > len(existing.description or "")) and opp.description:
                existing.description = opp.description
            if not existing.provider and opp.provider:
                existing.provider = opp.provider
            if not existing.company and opp.company:
                existing.company = opp.company
            if not existing.location and opp.location:
                existing.location = opp.location
            if (existing.category == "other" or not existing.category) and opp.category and opp.category != "other":
                existing.category = opp.category
            if (opp.score or 0) > (existing.score or 0):
                existing.score = opp.score
            if opp.last_seen:
                existing.last_seen = opp.last_seen

            self.upsert(existing)
            logger.info(f"Duplicate opportunity merged: '{opp.title}' -> canonical ID '{existing.id}'")
            return existing.id, True

        saved_id = self.upsert(opp)
        return saved_id, False

    def cleanup_database_duplicates(self) -> Dict[str, Any]:
        """
        Scans existing Opportunities table for duplicate url_hash groups, merges missing fields,
        repoints foreign key references, and marks redundant records with status='duplicate'.

        Survivor Strategy:
        1. Most complete record (deadline, published_date, description, company, provider, score, category)
        2. Most recent record (discovered_date / last_seen)
        3. Stable deterministic ID (alphanumeric) as final tie-breaker
        """
        stats: Dict[str, Any] = {
            "total_opportunities": 0,
            "unique_canonical_urls": 0,
            "duplicate_groups_found": 0,
            "records_merged": 0,
            "duplicates_cleaned": 0,
        }

        with self.db_manager.transaction() as cursor:
            cursor.execute("SELECT COUNT(*) FROM Opportunities;")
            row = cursor.fetchone()
            stats["total_opportunities"] = row[0] if row else 0

            cursor.execute("SELECT COUNT(DISTINCT url_hash) FROM Opportunities;")
            row = cursor.fetchone()
            stats["unique_canonical_urls"] = row[0] if row else 0

            # Single batch fetch of all rows belonging to duplicate url_hash groups
            cursor.execute(
                "SELECT id, title, url, source_id, category, description, deadline, published_date, "
                "discovered_date, company, provider, location, score, status, duplicate_of_id, last_seen, url_hash "
                "FROM Opportunities WHERE url_hash IN ("
                "    SELECT url_hash FROM Opportunities GROUP BY url_hash HAVING COUNT(*) > 1"
                ");"
            )
            rows = cursor.fetchall()

            if not rows:
                return stats

            # Group rows by url_hash in memory
            from collections import defaultdict
            groups = defaultdict(list)
            for row in rows:
                uh = row[16]
                rec = Opportunity(
                    id=str(row[0]),
                    title=str(row[1] or ""),
                    url=str(row[2] or ""),
                    source_id=str(row[3] or ""),
                    category=str(row[4] or "other"),
                    description=str(row[5]) if row[5] is not None else None,
                    deadline=str(row[6]) if row[6] is not None else None,
                    published_date=str(row[7]) if row[7] is not None else None,
                    discovered_date=str(row[8] or ""),
                    company=str(row[9]) if row[9] is not None else None,
                    provider=str(row[10]) if row[10] is not None else None,
                    location=str(row[11]) if row[11] is not None else None,
                    score=int(row[12] or 0),
                    status=str(row[13] or "active"),
                    duplicate_of_id=str(row[14]) if row[14] is not None else None,
                    last_seen=str(row[15]) if row[15] is not None else None,
                )
                groups[uh].append(rec)

            stats["duplicate_groups_found"] = len(groups)

            def sort_key(item: Opportunity):
                completeness = 0
                if item.deadline: completeness += 10
                if item.published_date: completeness += 5
                if item.description and len(item.description.strip()) > 20: completeness += 8
                if item.category and item.category != "other": completeness += 4
                if item.company: completeness += 3
                if item.provider: completeness += 3
                completeness += (item.score or 0)
                recency = str(item.last_seen or item.discovered_date or "")
                return (completeness, recency, item.id)

            dup_updates = []
            survivor_updates = []
            email_history_updates = []

            for uh, records in groups.items():
                if len(records) <= 1:
                    continue

                records.sort(key=sort_key, reverse=True)
                survivor = records[0]

                for dup in records[1:]:
                    # Merge metadata into survivor
                    if not survivor.deadline and dup.deadline:
                        survivor.deadline = dup.deadline
                    if not survivor.published_date and dup.published_date:
                        survivor.published_date = dup.published_date
                    if (not survivor.description or len(dup.description or "") > len(survivor.description or "")) and dup.description:
                        survivor.description = dup.description
                    if not survivor.provider and dup.provider:
                        survivor.provider = dup.provider
                    if not survivor.company and dup.company:
                        survivor.company = dup.company
                    if not survivor.location and dup.location:
                        survivor.location = dup.location
                    if (survivor.category == "other" or not survivor.category) and dup.category and dup.category != "other":
                        survivor.category = dup.category
                    if (dup.score or 0) > (survivor.score or 0):
                        survivor.score = dup.score

                    email_history_updates.append((survivor.id, dup.id))
                    dup_updates.append((Status.DUPLICATE.value, survivor.id, dup.id))
                    stats["duplicates_cleaned"] += 1

                survivor_updates.append((
                    survivor.deadline, survivor.published_date, survivor.description,
                    survivor.provider, survivor.company, survivor.location, survivor.category,
                    survivor.score, Status.ACTIVE.value, survivor.id
                ))
                stats["records_merged"] += 1

            if email_history_updates:
                try:
                    cursor.executemany(
                        "UPDATE EmailHistory SET opportunity_id = ? WHERE opportunity_id = ?;",
                        email_history_updates
                    )
                except Exception:
                    pass

            if dup_updates:
                cursor.executemany(
                    "UPDATE Opportunities SET status = ?, duplicate_of_id = ? WHERE id = ?;",
                    dup_updates
                )

            if survivor_updates:
                cursor.executemany(
                    "UPDATE Opportunities SET deadline = ?, published_date = ?, description = ?, "
                    "provider = ?, company = ?, location = ?, category = ?, score = ?, status = ? WHERE id = ?;",
                    survivor_updates
                )

        return stats
