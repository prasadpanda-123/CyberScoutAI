"""
PostgreSQL Persistent Repository for Server-Side Session State.

Provides secure storage, hashing, and lifecycle management for opaque server-side sessions,
eliminating sensitive identity, CSRF tokens, and application state from browser cookies.
"""

from datetime import datetime, timezone
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional

from src.core.exceptions import DatabaseError, RepositoryError
from src.core.logging import get_logger
from src.database.connection import DatabaseManager

logger = get_logger(__name__)


def hash_session_id(session_id: str) -> str:
    """Computes SHA-256 hash of an opaque session identifier."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def generate_session_id() -> str:
    """Generates a cryptographically secure opaque session identifier (256 bits entropy)."""
    return secrets.token_urlsafe(32)


class SessionRepository:
    """
    Repository managing the 'ServerSessions' table in PostgreSQL.
    Provides session creation, retrieval, updates, revocation, and automated cleanup.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensures 'ServerSessions' table, indexes, and RLS are configured idempotently."""
        sql = """
        CREATE TABLE IF NOT EXISTS "ServerSessions" (
            session_hash VARCHAR(64) PRIMARY KEY,
            session_data TEXT NOT NULL DEFAULT '{}',
            account_id VARCHAR(64) NULL,
            account_type VARCHAR(16) NOT NULL DEFAULT 'anonymous',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP NULL
        );
        CREATE INDEX IF NOT EXISTS ix_server_sessions_expires_at ON "ServerSessions"(expires_at);
        CREATE INDEX IF NOT EXISTS ix_server_sessions_account ON "ServerSessions"(account_id, account_type);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                try:
                    cursor.execute('ALTER TABLE "ServerSessions" ENABLE ROW LEVEL SECURITY;')
                    rls_policy_sql = """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'ServerSessions' AND policyname = 'server_sessions_access_policy') THEN
                            CREATE POLICY server_sessions_access_policy ON "ServerSessions" FOR ALL TO authenticated, service_role USING (true) WITH CHECK (true);
                        END IF;
                    END $$;
                    """
                    cursor.execute(rls_policy_sql)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"ServerSessions table initialization notice: {e}")

    def get_session(self, session_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves active unexpired, unrevoked session data by session hash.
        Returns parsed dict if valid, or None if expired/revoked/non-existent.
        """
        if not session_hash:
            return None

        sql = """
        SELECT session_data, expires_at, revoked_at
        FROM "ServerSessions"
        WHERE session_hash = %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (session_hash,))
                row = cursor.fetchone()
                if not row:
                    return None

                revoked_at = row["revoked_at"] if hasattr(row, "__getitem__") else getattr(row, "revoked_at", None)
                if revoked_at is not None:
                    return None

                expires_at = row["expires_at"] if hasattr(row, "__getitem__") else getattr(row, "expires_at", None)
                if expires_at is not None:
                    now = datetime.now(timezone.utc)
                    if isinstance(expires_at, datetime):
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        if now > expires_at:
                            return None
                    elif isinstance(expires_at, (int, float)):
                        if now.timestamp() > expires_at:
                            return None
                    elif isinstance(expires_at, str):
                        try:
                            parsed_exp = datetime.fromisoformat(expires_at)
                            if parsed_exp.tzinfo is None:
                                parsed_exp = parsed_exp.replace(tzinfo=timezone.utc)
                            if now > parsed_exp:
                                return None
                        except Exception:
                            pass

                raw_data = row["session_data"] if hasattr(row, "__getitem__") else getattr(row, "session_data", "{}")
                if isinstance(raw_data, str):
                    return json.loads(raw_data)
                elif isinstance(raw_data, dict):
                    return raw_data
                return {}
        except Exception as e:
            logger.warning(f"Error reading session from database: {e}")
            return None

    def save_session(
        self,
        session_hash: str,
        session_data: Dict[str, Any],
        expires_at: datetime,
        account_id: Optional[Any] = None,
        account_type: str = "anonymous",
    ) -> bool:
        """
        Persists or updates session data in PostgreSQL.
        Stores session data as serialized JSON and hashes identifier at rest.
        """
        if not session_hash:
            return False

        serialized = json.dumps(session_data, default=str)
        str_account_id = str(account_id) if account_id is not None else None

        sql = """
        INSERT INTO "ServerSessions" (
            session_hash, session_data, account_id, account_type, expires_at, last_seen_at, revoked_at
        ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, NULL)
        ON CONFLICT (session_hash) DO UPDATE SET
            session_data = EXCLUDED.session_data,
            account_id = EXCLUDED.account_id,
            account_type = EXCLUDED.account_type,
            expires_at = EXCLUDED.expires_at,
            last_seen_at = CURRENT_TIMESTAMP,
            revoked_at = NULL;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (session_hash, serialized, str_account_id, account_type, expires_at),
                )
            return True
        except Exception as e:
            logger.error(f"Error saving session {session_hash[:10]}... to database: {e}")
            return False

    def revoke_session(self, session_hash: str) -> bool:
        """Soft-revokes a session by setting revoked_at timestamp."""
        if not session_hash:
            return False
        sql = 'UPDATE "ServerSessions" SET revoked_at = CURRENT_TIMESTAMP WHERE session_hash = %s;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (session_hash,))
                return getattr(cursor, "rowcount", 0) > 0
        except Exception as e:
            logger.warning(f"Error revoking session: {e}")
            return False

    def delete_session(self, session_hash: str) -> bool:
        """Permanently removes a session record from the database."""
        if not session_hash:
            return False
        sql = 'DELETE FROM "ServerSessions" WHERE session_hash = %s;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (session_hash,))
                return getattr(cursor, "rowcount", 0) > 0
        except Exception as e:
            logger.warning(f"Error deleting session: {e}")
            return False

    def cleanup_expired(self) -> int:
        """Removes all expired and revoked sessions from the database."""
        sql = 'DELETE FROM "ServerSessions" WHERE expires_at < CURRENT_TIMESTAMP OR revoked_at IS NOT NULL;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                return getattr(cursor, "rowcount", 0)
        except Exception as e:
            logger.warning(f"Error cleaning up expired sessions: {e}")
            return 0
