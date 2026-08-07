"""
Opportunity Repository for CyberScout AI.

Handles database CRUD, upserts, duplicate management, and lifecycle status
updates for Opportunity objects in PostgreSQL.
"""

import json
from typing import Any, Dict, List, Optional

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
        if category:
            return self.search(
                where_clause="status = ? AND (is_rejected IS NOT TRUE) AND (expired = 0 OR expired IS NULL) AND (archived = 0 OR archived IS NULL) AND LOWER(category) = LOWER(?)",
                params=(Status.ACTIVE.value, category),
                order_by="score DESC, discovered_date DESC",
                limit=limit,
            )
        return self.search(
            where_clause="status = ? AND (is_rejected IS NOT TRUE) AND (expired = 0 OR expired IS NULL) AND (archived = 0 OR archived IS NULL)",
            params=(Status.ACTIVE.value,),
            order_by="score DESC, discovered_date DESC",
            limit=limit,
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
