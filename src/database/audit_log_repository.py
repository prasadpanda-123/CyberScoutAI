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
        event_type: str = "SYSTEM",
        action: str = "UNKNOWN",
        status: str = "SUCCESS",
        user_id: Optional[Any] = None,
        username: Optional[str] = None,
        source_ip: Optional[str] = None,
        details: Optional[str] = None,
        category: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Records a new administrative audit event in the AuditLogs table.
        Polymorphic: safely handles user UUIDs, admin integer IDs, and system events (SEC-03).
        """
        resolved_event_type = category or event_type or "SYSTEM"
        ts = datetime.now(timezone.utc).isoformat()
        safe_user_id = None
        current_username = username
        current_details = details or ""

        if user_id is not None:
            # 1. Attempt to resolve as User UUID
            is_uuid = False
            candidate_uuid = None
            try:
                import uuid
                candidate_uuid = str(uuid.UUID(str(user_id).strip()))
                is_uuid = True
            except (ValueError, TypeError, AttributeError):
                is_uuid = False

            if is_uuid and candidate_uuid:
                # Verify that candidate_id exists in Users table to satisfy fk_auditlogs_user_id constraint
                try:
                    conn = self.db_manager.get_connection()
                    chk_cursor = conn.cursor()
                    try:
                        chk_cursor.execute('SELECT username FROM "Users" WHERE id = %s LIMIT 1;', (candidate_uuid,))
                        u_row = chk_cursor.fetchone()
                        if u_row:
                            safe_user_id = candidate_uuid
                            if not current_username or current_username == "Anonymous":
                                current_username = u_row[0]
                        else:
                            safe_user_id = None
                            extra_detail = f"[unresolved_user_id: {candidate_uuid}]"
                            if extra_detail not in current_details:
                                current_details = f"{current_details} {extra_detail}".strip()
                    finally:
                        chk_cursor.close()
                except Exception:
                    safe_user_id = None
            else:
                # 2. Candidate is not a UUID - check if integer Admin ID from Admins table
                is_admin_id = False
                admin_int = None
                try:
                    admin_int = int(str(user_id).strip())
                    is_admin_id = True
                except (ValueError, TypeError):
                    is_admin_id = False

                if is_admin_id and admin_int is not None:
                    try:
                        conn = self.db_manager.get_connection()
                        chk_cursor = conn.cursor()
                        try:
                            chk_cursor.execute('SELECT username FROM "Admins" WHERE id = %s LIMIT 1;', (admin_int,))
                            a_row = chk_cursor.fetchone()
                            if a_row:
                                # Preserves PostgreSQL fk_auditlogs_user_id -> Users(id) integrity
                                safe_user_id = None
                                if not current_username or current_username == "Anonymous":
                                    current_username = a_row[0]
                                extra_detail = f"[admin_id: {admin_int}]"
                                if extra_detail not in current_details:
                                    current_details = f"{current_details} {extra_detail}".strip()
                            else:
                                safe_user_id = None
                                extra_detail = f"[unresolved_admin_id: {admin_int}]"
                                if extra_detail not in current_details:
                                    current_details = f"{current_details} {extra_detail}".strip()
                        finally:
                            chk_cursor.close()
                    except Exception:
                        safe_user_id = None
                else:
                    # 3. System, cron, scheduler, or non-numeric identity
                    safe_user_id = None
                    raw_id = str(user_id).strip()
                    if raw_id.upper() in ("SYSTEM", "ANONYMOUS", "CRON", "SCHEDULER"):
                        if not current_username:
                            current_username = raw_id.upper()
                    else:
                        extra_detail = f"[unresolved_identity: {raw_id}]"
                        if extra_detail not in current_details:
                            current_details = f"{current_details} {extra_detail}".strip()

        sql = """
        INSERT INTO "AuditLogs" (timestamp, user_id, username, event_type, action, source_ip, status, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (
                        ts,
                        safe_user_id,
                        current_username or "Anonymous",
                        resolved_event_type,
                        action,
                        source_ip or "127.0.0.1",
                        status,
                        current_details or "",
                    ),
                )
            return {
                "timestamp": ts,
                "user_id": safe_user_id,
                "username": current_username or "Anonymous",
                "event_type": resolved_event_type,
                "action": action,
                "source_ip": source_ip or "127.0.0.1",
                "status": status,
                "details": current_details or "",
            }
        except Exception as e:
            from src.core.logging import get_logger
            get_logger(__name__).error(f"Could not record audit log: {e}")
            return {"status": "failed", "error": str(e)}

    def query_logs(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[Any] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Retrieves paginated audit log entries with optional filters.
        Safely searches user UUIDs or admin integer identities and escapes LIKE wildcards (SEC-07).
        """
        page = max(1, int(page))
        limit = max(1, min(int(limit), 200))
        where_clauses: List[str] = []
        params: List[Any] = []

        if event_type and event_type.upper() != "ALL":
            where_clauses.append('"event_type" = %s')
            params.append(event_type)

        if user_id is not None:
            is_uuid = False
            candidate_uuid = None
            try:
                import uuid
                candidate_uuid = str(uuid.UUID(str(user_id).strip()))
                is_uuid = True
            except (ValueError, TypeError, AttributeError):
                is_uuid = False

            if is_uuid and candidate_uuid:
                where_clauses.append('"user_id" = %s')
                params.append(candidate_uuid)
            else:
                raw_id_str = str(user_id).strip()
                where_clauses.append('("details" LIKE %s OR "username" = %s)')
                params.append(f"%[admin_id: {raw_id_str}]%")
                params.append(raw_id_str)

        if status and status.upper() != "ALL":
            where_clauses.append('"status" = %s')
            params.append(status)

        if search_query:
            # Escape %, _, and \ for SEC-07 wildcard injection mitigation
            escaped_q = search_query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped_q}%"
            where_clauses.append('("username" LIKE %s OR "action" LIKE %s OR "details" LIKE %s OR "source_ip" LIKE %s)')
            params.extend([pattern, pattern, pattern, pattern])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_sql = f'SELECT COUNT(*) FROM "AuditLogs"{where_sql}'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(count_sql, params)
            count_row = cursor.fetchone()
            total_records = int(count_row[0]) if (count_row is not None and count_row[0] is not None) else 0

            offset = max(0, (page - 1) * limit)
            data_sql = f'SELECT id, timestamp, user_id, username, event_type, action, source_ip, status, details FROM "AuditLogs"{where_sql} ORDER BY id DESC LIMIT %s OFFSET %s'
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
