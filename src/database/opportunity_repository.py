"""
Opportunity Repository for CyberScout AI.

Handles database CRUD, upserts, duplicate management, and lifecycle status
updates for Opportunity objects in SQLite.
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
    DAO for managing Opportunity records in SQLite.
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
            "remote": 1 if opp.remote else 0,
            "paid": 1 if opp.paid is True else (0 if opp.paid is False else None),
            "certificate": 1 if opp.certificate else 0,
            "price_raw": opp.price_raw,
            "price_normalized": opp.price_normalized,
            "currency": opp.currency,
            "deadline": opp.deadline,
            "published_date": opp.published_date,
            "discovered_date": opp.discovered_date,
            "duration": opp.duration,
            "difficulty": opp.difficulty,
            "tags": json.dumps(opp.tags),
            "beginner_friendly": 1 if opp.beginner_friendly is True else (0 if opp.beginner_friendly is False else None),
            "score": opp.score,
            "score_breakdown": json.dumps(opp.score_breakdown),
            "status": opp.status,
            "duplicate_of_id": opp.duplicate_of_id,
            "run_id": opp.run_id,
            "raw_data": json.dumps(opp.raw_data),
            "last_seen": opp.last_seen,
        }

    def _row_to_entity(self, row: Any) -> Opportunity:
        tags = json.loads(row["tags"]) if row["tags"] else []
        score_breakdown = json.loads(row["score_breakdown"]) if row["score_breakdown"] else {}
        raw_data = json.loads(row["raw_data"]) if row["raw_data"] else {}

        return Opportunity(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            url=row["url"],
            source_id=row["source_id"],
            category=row["category"],
            provider=row["provider"],
            company=row["company"],
            location=row["location"],
            remote=bool(row["remote"]),
            paid=bool(row["paid"]) if row["paid"] is not None else None,
            certificate=bool(row["certificate"]),
            price_raw=row["price_raw"],
            price_normalized=row["price_normalized"],
            currency=row["currency"],
            deadline=row["deadline"],
            published_date=row["published_date"],
            discovered_date=row["discovered_date"],
            duration=row["duration"],
            difficulty=row["difficulty"],
            tags=tags,
            beginner_friendly=bool(row["beginner_friendly"]) if row["beginner_friendly"] is not None else None,
            score=row["score"],
            score_breakdown=score_breakdown,
            status=row["status"],
            duplicate_of_id=row["duplicate_of_id"],
            run_id=row["run_id"],
            raw_data=raw_data,
            last_seen=row["last_seen"],
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
            score, score_breakdown, status, duplicate_of_id, run_id,
            raw_data, last_seen
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            score = excluded.score,
            score_breakdown = excluded.score_breakdown,
            status = excluded.status,
            last_seen = excluded.last_seen;
        """
        values = (
            data["id"], data["title"], data["description"], data["url"], data["url_hash"],
            data["source_id"], data["category"], data["provider"], data["company"], data["location"],
            data["remote"], data["paid"], data["certificate"], data["price_raw"], data["price_normalized"],
            data["currency"], data["deadline"], data["published_date"], data["discovered_date"], data["duration"],
            data["difficulty"], data["tags"], data["beginner_friendly"], data["score"], data["score_breakdown"],
            data["status"], data["duplicate_of_id"], data["run_id"], data["raw_data"], data["last_seen"]
        )

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
            return opp.id
        except Exception as e:
            raise RepositoryError(f"Failed to upsert Opportunity '{opp.id}': {e}", original_exception=e)

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
                where_clause="status = ? AND category = ?",
                params=(Status.ACTIVE.value, category),
                order_by="score DESC, discovered_date DESC",
                limit=limit,
            )
        return self.search(
            where_clause="status = ?",
            params=(Status.ACTIVE.value,),
            order_by="score DESC, discovered_date DESC",
            limit=limit,
        )

    def update_status(self, opp_id: str, new_status: str) -> None:
        sql = "UPDATE Opportunities SET status = ? WHERE id = ?;"
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (new_status, opp_id))

    def mark_as_duplicate(self, opp_id: str, canonical_id: str) -> None:
        sql = "UPDATE Opportunities SET status = ?, duplicate_of_id = ? WHERE id = ?;"
        with self.db_manager.transaction() as cursor:
            cursor.execute(sql, (Status.DUPLICATE.value, canonical_id, opp_id))
