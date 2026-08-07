"""
Source Repository for CyberScout AI.

Syncs registered sources from sources.yaml into SQLite and queries source definitions.
"""

from typing import Any, Dict, List, Optional

from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.interfaces import ISourceRepository
from src.models.source import Source
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)


class SourceRepository(BaseRepository[Source], ISourceRepository):
    """
    DAO for managing target Sources in SQLite.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        super().__init__(db_manager=db_manager)

    @property
    def table_name(self) -> str:
        return "Sources"

    @property
    def primary_key(self) -> str:
        return "id"

    def _entity_to_dict(self, source: Source) -> Dict[str, Any]:
        return {
            "id": source.id,
            "name": source.name,
            "collection_method": source.collection_method,
            "default_category": source.default_category,
            "status": source.status,
            "enabled": bool(source.enabled),
            "official": bool(source.official),
            "trust_score": source.trust_score,
            "maintenance_level": source.maintenance_level,
            "update_frequency": source.update_frequency,
            "max_requests_per_run": source.max_requests_per_run,
            "request_delay_ms": source.request_delay_ms,
        }

    def _row_to_entity(self, row: Any) -> Source:
        return Source(
            id=row["id"],
            name=row["name"],
            collection_method=row["collection_method"],
            default_category=row["default_category"],
            status=row["status"],
            enabled=bool(row["enabled"]),
            official=bool(row["official"]),
            trust_score=row["trust_score"],
            maintenance_level=row["maintenance_level"],
            update_frequency=row["update_frequency"],
            max_requests_per_run=row["max_requests_per_run"],
            request_delay_ms=row["request_delay_ms"],
        )

    def save_source(self, source: Source) -> str:
        """Upserts a source record idempotently."""
        data = self._entity_to_dict(source)
        sql = """
        INSERT INTO Sources (
            id, name, collection_method, default_category, status,
            enabled, official, trust_score, maintenance_level,
            update_frequency, max_requests_per_run, request_delay_ms
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            collection_method = excluded.collection_method,
            default_category = excluded.default_category,
            status = excluded.status,
            enabled = excluded.enabled,
            trust_score = excluded.trust_score;
        """
        values = (
            data["id"], data["name"], data["collection_method"], data["default_category"],
            data["status"], data["enabled"], data["official"], data["trust_score"],
            data["maintenance_level"], data["update_frequency"], data["max_requests_per_run"],
            data["request_delay_ms"]
        )
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
            return source.id
        except Exception as e:
            raise RepositoryError(f"Failed to save Source '{source.id}': {e}", original_exception=e)

    def sync_from_config(self, sources_config: Dict[str, Any]) -> int:
        """
        Syncs source records from loaded sources config dictionary into the database.

        Args:
            sources_config: Master dictionary of sources from config.

        Returns:
            Number of synced source records.
        """
        synced_count = 0
        try:
            sources_list = (
                sources_config.get("sources", [])
                if isinstance(sources_config, dict) and "sources" in sources_config
                else sources_config
            )

            if isinstance(sources_list, dict):
                source_items = [
                    {"id": k, **v} if isinstance(v, dict) else {"id": k}
                    for k, v in sources_list.items()
                ]
            elif isinstance(sources_list, list):
                source_items = sources_list
            else:
                source_items = []

            for item in source_items:
                if not isinstance(item, dict) or "id" not in item:
                    continue

                source_obj = Source(
                    id=item["id"],
                    name=item.get("name", item["id"].capitalize()),
                    collection_method=item.get("collection_method", item.get("type", "rss")),
                    default_category=item.get("default_category", "other"),
                    status=item.get("status", "active"),
                    enabled=bool(item.get("enabled", True)),
                    official=bool(item.get("official", False)),
                    trust_score=float(item.get("trust_score", 1.0)),
                    maintenance_level=item.get("maintenance_level", "stable"),
                    update_frequency=item.get("update_frequency", "daily"),
                    max_requests_per_run=item.get("max_requests_per_run", 10),
                    request_delay_ms=item.get("request_delay_ms", 1000),
                )
                self.save_source(source_obj)
                synced_count += 1
            logger.info(f"Synced {synced_count} source records into database.")
            return synced_count
        except Exception as e:
            raise RepositoryError(f"Failed to sync sources config to database: {e}", original_exception=e)

    def get_active_sources(self) -> List[Source]:
        """Retrieves all enabled sources from database."""
        return self.search(where_clause="(enabled IS TRUE OR enabled = True)")

    def get_sources_by_method(self, method: str) -> List[Source]:
        """Retrieves active sources matching a specific collection method."""
        return self.search(where_clause="collection_method = ? AND (enabled IS TRUE OR enabled = True)", params=(method,))
