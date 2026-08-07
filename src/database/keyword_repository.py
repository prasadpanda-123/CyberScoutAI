"""
Keyword Repository for CyberScout AI.

Handles database operations for taxonomy terms in Keywords table.
"""

from typing import Any, Dict, List, Optional

from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.interfaces import IKeywordRepository
from src.models.keyword import Keyword
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)


class KeywordRepository(BaseRepository[Keyword], IKeywordRepository):
    """
    DAO for managing Keyword taxonomy terms in PostgreSQL.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        super().__init__(db_manager=db_manager)

    @property
    def table_name(self) -> str:
        return "Keywords"

    @property
    def primary_key(self) -> str:
        return "id"

    def _entity_to_dict(self, keyword: Keyword) -> Dict[str, Any]:
        return {
            "id": keyword.id,
            "term": keyword.term,
            "domain": keyword.domain,
            "synonym_of": keyword.synonym_of,
        }

    def _row_to_entity(self, row: Any) -> Keyword:
        return Keyword(
            id=row["id"],
            term=row["term"],
            domain=row["domain"],
            synonym_of=row["synonym_of"],
        )

    def save_keyword(self, keyword: Keyword) -> str:
        """Saves or updates a keyword record."""
        sql = """
        INSERT INTO Keywords (id, term, domain, synonym_of)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            term = excluded.term,
            domain = excluded.domain,
            synonym_of = excluded.synonym_of;
        """
        data = self._entity_to_dict(keyword)
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (data["id"], data["term"], data["domain"], data["synonym_of"]))
            return keyword.id
        except Exception as e:
            raise RepositoryError(f"Failed to save Keyword '{keyword.term}': {e}", original_exception=e)

    def get_keywords_by_domain(self, domain: str) -> List[Keyword]:
        """Retrieves keywords matching a specific domain."""
        return self.search(where_clause="domain = ?", params=(domain,))
