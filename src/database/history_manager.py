"""
History Manager for CyberScout AI.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from src.database.connection import DatabaseManager


class HistoryManager:
    """
    Logs opportunity state changes, search executions, and pipeline runs into DB history tables.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def record_opportunity_change(self, opportunity_id: str, change_type: str, old_val: Optional[str] = None, new_val: Optional[str] = None) -> None:
        """Records an entry in opportunity_history."""
        rec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO opportunity_history (id, opportunity_id, change_type, old_value, new_value, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (rec_id, opportunity_id, change_type, old_val, new_val, now))
        except Exception:
            pass
