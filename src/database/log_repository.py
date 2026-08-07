"""
Structured Log Repository for CyberScout AI.

Persists and queries structured log entries from the PostgreSQL AppLogs table.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.database.connection import DatabaseManager


class LogRepository:
    """
    Repository for persisting and querying structured system logs.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def insert_log(
        self,
        level: str,
        module: str,
        message: str,
        function_name: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
        exception_text: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """
        Inserts a single log entry into AppLogs.
        """
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql = """
        INSERT INTO AppLogs (timestamp, level, module, function_name, message, execution_time_ms, exception_text, correlation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (
                        ts,
                        level.upper(),
                        module,
                        function_name,
                        message,
                        execution_time_ms,
                        exception_text,
                        correlation_id,
                    ),
                )
                return cursor.lastrowid
        except Exception:
            return -1

    def query_logs(
        self,
        level: Optional[str] = None,
        module: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Queries AppLogs with filtering, search, pagination, and total count.
        """
        offset = max(0, (page - 1) * limit)
        conditions: List[str] = []
        params: List[Any] = []

        if level and level.upper() != "ALL":
            conditions.append("level = ?")
            params.append(level.upper())

        if module and module.lower() != "all":
            conditions.append("module LIKE ?")
            params.append(f"%{module}%")

        if search_query:
            conditions.append("(message LIKE ? OR function_name LIKE ? OR exception_text LIKE ?)")
            q = f"%{search_query}%"
            params.extend([q, q, q])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_sql = f"SELECT COUNT(*) FROM AppLogs {where_clause}"
        select_sql = f"""
        SELECT id, timestamp, level, module, function_name, message, execution_time_ms, exception_text, correlation_id
        FROM AppLogs {where_clause}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """

        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(count_sql, params)
            total_count = cursor.fetchone()[0]

            cursor.execute(select_sql, params + [limit, offset])
            rows = cursor.fetchall()

            logs = []
            for row in rows:
                logs.append(
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "level": row["level"],
                        "module": row["module"],
                        "function_name": row["function_name"],
                        "message": row["message"],
                        "execution_time_ms": row["execution_time_ms"],
                        "exception_text": row["exception_text"],
                        "correlation_id": row["correlation_id"],
                    }
                )

            total_pages = max(1, (total_count + limit - 1) // limit)
            return {
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "logs": logs,
            }
        finally:
            cursor.close()

    def get_log_stats(self) -> Dict[str, Any]:
        """
        Returns structured summary counts grouped by log severity and active modules.
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT level, COUNT(*) as count FROM AppLogs GROUP BY level")
            level_counts = {row["level"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT DISTINCT module FROM AppLogs LIMIT 50")
            modules = [row["module"] for row in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) FROM AppLogs")
            total = cursor.fetchone()[0]

            return {
                "total_logs": total,
                "info_count": level_counts.get("INFO", 0),
                "warning_count": level_counts.get("WARNING", 0),
                "error_count": level_counts.get("ERROR", 0),
                "debug_count": level_counts.get("DEBUG", 0),
                "modules": modules,
            }
        finally:
            cursor.close()
