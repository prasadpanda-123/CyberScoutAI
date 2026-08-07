"""
Audit Log Repository for CyberScout AI Security & Administration.

Stores and queries structured administrative audit logs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.database.connection import DatabaseManager


class AuditLogRepository:
    """
    Repository for managing audit entries in the AuditLogs table.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def log_event(
        self,
        event_type: str,
        action: str,
        status: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        source_ip: Optional[str] = None,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records a new administrative audit event in the AuditLogs table.
        """
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql = """
        INSERT INTO AuditLogs (timestamp, user_id, username, event_type, action, source_ip, status, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                sql,
                (
                    ts,
                    user_id,
                    username or "Anonymous",
                    event_type,
                    action,
                    source_ip or "127.0.0.1",
                    status,
                    details or "",
                ),
            )
            conn.commit()
            log_id = cursor.lastrowid
            return {
                "id": log_id,
                "timestamp": ts,
                "user_id": user_id,
                "username": username or "Anonymous",
                "event_type": event_type,
                "action": action,
                "source_ip": source_ip or "127.0.0.1",
                "status": status,
                "details": details or "",
            }
        except Exception as e:
            conn.rollback()
            from src.core.logging import get_logger
            get_logger(__name__).warning(f"Could not record audit log: {e}")
            return {"status": "failed", "error": str(e)}
        finally:
            cursor.close()

    def query_logs(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Retrieves paginated audit log entries with optional filters.
        """
        where_clauses: List[str] = []
        params: List[Any] = []

        if event_type and event_type.upper() != "ALL":
            where_clauses.append("event_type = ?")
            params.append(event_type)

        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)

        if status and status.upper() != "ALL":
            where_clauses.append("status = ?")
            params.append(status)

        if search_query:
            where_clauses.append("(username LIKE ? OR action LIKE ? OR details LIKE ? OR source_ip LIKE ?)")
            pattern = f"%{search_query.strip()}%"
            params.extend([pattern, pattern, pattern, pattern])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_sql = f"SELECT COUNT(*) FROM AuditLogs{where_sql}"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(count_sql, params)
            count_row = cursor.fetchone()
            total_records = count_row[0] if count_row and len(count_row) > 0 and count_row[0] is not None else 0

            offset = max(0, (page - 1) * limit)
            data_sql = f"SELECT id, timestamp, user_id, username, event_type, action, source_ip, status, details FROM AuditLogs{where_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
            cursor.execute(data_sql, params + [limit, offset])
            rows = cursor.fetchall() or []
            from src.database.base_repository import row_to_dict
            logs = [row_to_dict(r) for r in rows] if rows else []

            total_pages = max(1, (total_records + limit - 1) // limit) if total_records > 0 else 1

            return {
                "logs": logs,
                "total_records": total_records,
                "total_pages": total_pages,
                "current_page": page,
                "limit": limit,
            }
        finally:
            cursor.close()
