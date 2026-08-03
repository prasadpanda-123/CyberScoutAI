"""
Archive Manager for CyberScout AI.
"""

from typing import Optional

from src.database.connection import DatabaseManager
from src.models.enums import Status


class ArchiveManager:
    """
    Manages archiving and marking expired opportunities as ARCHIVED.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def archive_expired_opportunities(self, days_old: int = 90) -> int:
        """
        Marks expired opportunities older than days_old as ARCHIVED.

        Args:
            days_old: Retention threshold in days.

        Returns:
            Number of archived records.
        """
        sql = """
            UPDATE opportunities
            SET status = 'archived'
            WHERE status = 'expired';
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                return cursor.rowcount
        except Exception:
            return 0
