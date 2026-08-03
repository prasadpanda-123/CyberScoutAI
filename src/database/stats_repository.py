"""
Statistics and Preferences Repositories for CyberScout AI.
"""

from typing import Any, Dict, List, Optional

from src.database.base_repository import BaseRepository
from src.database.connection import DatabaseManager
from src.database.interfaces import IPreferencesRepository, IStatisticsRepository
from src.models.stats import ApplicationStatistics, Preferences
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)


class StatisticsRepository(BaseRepository[ApplicationStatistics], IStatisticsRepository):
    """
    DAO for managing operational metrics in Statistics table.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        super().__init__(db_manager=db_manager)

    @property
    def table_name(self) -> str:
        return "Statistics"

    @property
    def primary_key(self) -> str:
        return "id"

    def _entity_to_dict(self, stats: ApplicationStatistics) -> Dict[str, Any]:
        return {
            "id": stats.id,
            "date": stats.date,
            "source_id": stats.source_id,
            "category": stats.category,
            "count": stats.count,
            "avg_score": stats.avg_score,
        }

    def _row_to_entity(self, row: Any) -> ApplicationStatistics:
        return ApplicationStatistics(
            id=row["id"],
            date=row["date"],
            source_id=row["source_id"],
            category=row["category"],
            count=row["count"],
            avg_score=row["avg_score"],
        )

    def record_statistics(self, stats: ApplicationStatistics) -> str:
        """Records an operational metrics entry."""
        return self.create(stats)

    def get_statistics_by_date(self, date_str: str) -> List[ApplicationStatistics]:
        """Retrieves metrics entries for a target date."""
        return self.search(where_clause="date = ?", params=(date_str,))


class PreferencesRepository(BaseRepository[Preferences], IPreferencesRepository):
    """
    DAO for managing user preferences in Preferences table.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        super().__init__(db_manager=db_manager)

    @property
    def table_name(self) -> str:
        return "Preferences"

    @property
    def primary_key(self) -> str:
        return "id"

    def _entity_to_dict(self, pref: Preferences) -> Dict[str, Any]:
        return {
            "id": pref.id,
            "key": pref.key,
            "value": pref.value,
            "updated_at": pref.updated_at,
        }

    def _row_to_entity(self, row: Any) -> Preferences:
        return Preferences(
            id=row["id"],
            key=row["key"],
            value=row["value"],
            updated_at=row["updated_at"],
        )

    def set_preference(self, key: str, value: str) -> None:
        """Sets or updates a user preference key-value pair."""
        sql = """
        INSERT INTO Preferences (id, key, value, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now');
        """
        import uuid
        pref_id = str(uuid.uuid4())
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (pref_id, key, value))
        except Exception as e:
            raise RepositoryError(f"Failed to set preference '{key}': {e}", original_exception=e)

    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves a preference value by key."""
        results = self.search(where_clause="key = ?", params=(key,), limit=1)
        if results:
            return results[0].value
        return default
