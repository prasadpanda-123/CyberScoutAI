"""
PostgreSQL Persistent Repository for Pending MFA and OTP Verification States.

Replaces process-local in-memory stores, enabling stateless multi-worker WSGI
concurrency without sticky sessions.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, Optional

from src.core.exceptions import DatabaseError, RepositoryError
from src.core.logging import get_logger
from src.database.base_repository import row_to_dict
from src.database.connection import DatabaseManager

logger = get_logger(__name__)


class MfaRepository:
    """
    Repository managing the 'PendingMfa' table in PostgreSQL.
    Centralizes OTP hashes, attempt counters, and transaction state.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensures 'PendingMfa' table, indexes, and RLS are configured idempotently."""
        sql = """
        CREATE TABLE IF NOT EXISTS "PendingMfa" (
            token VARCHAR(64) PRIMARY KEY,
            state_type VARCHAR(32) NOT NULL DEFAULT 'admin_login_mfa',
            account_id INTEGER NOT NULL,
            username VARCHAR(128) NOT NULL,
            email VARCHAR(255) NOT NULL,
            role VARCHAR(64) NULL,
            otp_hash VARCHAR(64) NOT NULL,
            new_password_hash TEXT NULL,
            next_url TEXT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            expires_at INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_resend_at INTEGER NULL
        );
        CREATE INDEX IF NOT EXISTS ix_pending_mfa_account_state ON "PendingMfa"(account_id, state_type);
        CREATE INDEX IF NOT EXISTS ix_pending_mfa_expires_at ON "PendingMfa"(expires_at);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                try:
                    cursor.execute('ALTER TABLE "PendingMfa" ENABLE ROW LEVEL SECURITY;')
                    rls_policy_sql = """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'PendingMfa' AND policyname = 'pending_mfa_access_policy') THEN
                            CREATE POLICY pending_mfa_access_policy ON "PendingMfa" FOR ALL TO authenticated, service_role USING (true) WITH CHECK (true);
                        END IF;
                    END $$;
                    """
                    cursor.execute(rls_policy_sql)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"PendingMfa table initialization notice: {e}")

    def cleanup_expired(self) -> int:
        """Prunes all expired pending MFA records from the database."""
        now = int(time.time())
        sql = 'DELETE FROM "PendingMfa" WHERE expires_at < %s;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (now,))
                return getattr(cursor, "rowcount", 0)
        except Exception as e:
            logger.debug(f"Error cleaning up expired MFA records: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Admin MFA Login Methods
    # -------------------------------------------------------------------------

    def store_pending_mfa(
        self,
        token: str,
        user_id: int,
        username: str,
        email: str,
        role: str,
        otp_hash: str,
        expires_at: int,
        next_url: str = "",
        max_attempts: int = 5,
    ) -> str:
        """
        Persists a pending admin MFA verification session in PostgreSQL.
        """
        now = int(time.time())
        # Clean up existing sessions for this admin to prevent dangling rows
        cleanup_sql = 'DELETE FROM "PendingMfa" WHERE account_id = %s AND state_type = %s;'
        insert_sql = """
        INSERT INTO "PendingMfa" (
            token, state_type, account_id, username, email, role,
            otp_hash, next_url, attempts, max_attempts, expires_at, last_resend_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        with self.db_manager.transaction() as cursor:
            try:
                cursor.execute(cleanup_sql, (user_id, "admin_login_mfa"))
            except Exception:
                pass
            cursor.execute(
                insert_sql,
                (
                    token,
                    "admin_login_mfa",
                    user_id,
                    username,
                    email,
                    role,
                    otp_hash,
                    next_url,
                    0,
                    max_attempts,
                    expires_at,
                    now,
                ),
            )
        return token

    def get_pending_mfa(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Retrieves active pending MFA state by token. Returns None if expired or nonexistent.
        """
        if not token or not isinstance(token, str):
            return None

        sql = 'SELECT * FROM "PendingMfa" WHERE token = %s AND state_type = %s LIMIT 1;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (token.strip(), "admin_login_mfa"))
                row = cursor.fetchone()
                if not row:
                    return None
                data = row_to_dict(row, cursor.description)
                now = int(time.time())
                if now > int(data.get("expires_at", 0)):
                    cursor.execute('DELETE FROM "PendingMfa" WHERE token = %s;', (token.strip(),))
                    return None
                return {
                    "user_id": data.get("account_id"),
                    "username": data.get("username"),
                    "email": data.get("email"),
                    "role": data.get("role", "Admin"),
                    "otp_hash": data.get("otp_hash"),
                    "expires_at": data.get("expires_at"),
                    "attempts": data.get("attempts", 0),
                    "next_url": data.get("next_url", ""),
                    "last_resend_at": data.get("last_resend_at", 0),
                }
        except Exception as e:
            logger.warning(f"Error querying pending MFA token '{token}': {e}")
            return None

    def update_pending_mfa_otp(self, token: str, otp_hash: str, expires_at: int) -> bool:
        """
        Updates OTP hash, resets attempts to 0, and updates expiration and last_resend_at.
        Used when an administrator requests an OTP resend.
        """
        if not token or not isinstance(token, str):
            return False
        sql = '''
            UPDATE "PendingMfa" 
            SET otp_hash = %s, expires_at = %s, attempts = 0, last_resend_at = %s 
            WHERE token = %s AND state_type = %s;
        '''
        now = int(time.time())
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (otp_hash, expires_at, now, token.strip(), "admin_login_mfa"))
                return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"Error updating pending MFA OTP for token '{token}': {e}")
            return False

    def increment_pending_mfa_attempts(self, token: str) -> int:
        """Increments attempt count for a pending MFA session atomically in PostgreSQL."""
        if not token or not isinstance(token, str):
            return 0

        update_sql = 'UPDATE "PendingMfa" SET attempts = attempts + 1 WHERE token = %s;'
        select_sql = 'SELECT attempts FROM "PendingMfa" WHERE token = %s LIMIT 1;'
        with self.db_manager.transaction() as cursor:
            cursor.execute(update_sql, (token.strip(),))
            cursor.execute(select_sql, (token.strip(),))
            row = cursor.fetchone()
            if row:
                d = row_to_dict(row, cursor.description)
                return int(d.get("attempts", 0))
        return 0

    def clear_pending_mfa(self, token: Optional[str]) -> None:
        """Deletes pending MFA session from PostgreSQL."""
        if not token or not isinstance(token, str):
            return
        sql = 'DELETE FROM "PendingMfa" WHERE token = %s;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (token.strip(),))
        except Exception as e:
            logger.debug(f"Error clearing pending MFA token: {e}")

    # -------------------------------------------------------------------------
    # Password Change OTP Verification Methods
    # -------------------------------------------------------------------------

    def store_pending_password_change(
        self,
        token: str,
        target_type: str,
        account_id: int,
        username: str,
        email: str,
        new_password_hash: str,
        otp_hash: str,
        expires_at: int,
        max_attempts: int = 5,
    ) -> str:
        """Persists pending password change transaction in PostgreSQL."""
        now = int(time.time())
        state_type = f"{target_type.strip().lower()}_pw_change"
        cleanup_sql = 'DELETE FROM "PendingMfa" WHERE account_id = %s AND state_type = %s;'
        insert_sql = """
        INSERT INTO "PendingMfa" (
            token, state_type, account_id, username, email,
            new_password_hash, otp_hash, attempts, max_attempts, expires_at, last_resend_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        with self.db_manager.transaction() as cursor:
            try:
                cursor.execute(cleanup_sql, (account_id, state_type))
            except Exception:
                pass
            cursor.execute(
                insert_sql,
                (
                    token,
                    state_type,
                    account_id,
                    username,
                    email,
                    new_password_hash,
                    otp_hash,
                    0,
                    max_attempts,
                    expires_at,
                    now,
                ),
            )
        return token

    def get_pending_password_change(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Retrieves active pending password change transaction."""
        if not token or not isinstance(token, str):
            return None

        sql = 'SELECT * FROM "PendingMfa" WHERE token = %s AND state_type LIKE %s LIMIT 1;'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (token.strip(), "%_pw_change"))
            row = cursor.fetchone()
            if not row:
                return None
            data = row_to_dict(row, cursor.description)
            now = int(time.time())
            if now > int(data.get("expires_at", 0)):
                self.clear_pending_password_change(token)
                return None
            target_type = str(data.get("state_type", "user_pw_change")).replace("_pw_change", "")
            created_at_raw = data.get("created_at")
            created_epoch = now
            if hasattr(created_at_raw, "timestamp"):
                created_epoch = int(created_at_raw.timestamp())
            return {
                "target_type": target_type,
                "account_id": data.get("account_id"),
                "username": data.get("username"),
                "email": data.get("email"),
                "new_password_hash": data.get("new_password_hash"),
                "otp_hash": data.get("otp_hash"),
                "expires_at": data.get("expires_at"),
                "attempts": data.get("attempts", 0),
                "created_at": created_epoch,
                "last_resend_at": data.get("last_resend_at", created_epoch),
            }
        except Exception as e:
            logger.warning(f"Error querying pending password change token: {e}")
            return None
        finally:
            cursor.close()

    def increment_pending_password_change_attempts(self, token: str) -> int:
        """Increments attempt count for pending password change transaction."""
        if not token or not isinstance(token, str):
            return 0

        update_sql = 'UPDATE "PendingMfa" SET attempts = attempts + 1 WHERE token = %s;'
        select_sql = 'SELECT attempts FROM "PendingMfa" WHERE token = %s LIMIT 1;'
        with self.db_manager.transaction() as cursor:
            cursor.execute(update_sql, (token.strip(),))
            cursor.execute(select_sql, (token.strip(),))
            row = cursor.fetchone()
            if row:
                d = row_to_dict(row, cursor.description)
                return int(d.get("attempts", 0))
        return 0

    def update_pending_password_change_otp(
        self,
        token: str,
        new_otp_hash: str,
        new_expires_at: int,
    ) -> bool:
        """Updates OTP hash and resets attempt counter on resend."""
        if not token or not isinstance(token, str):
            return False

        now = int(time.time())
        update_sql = """
        UPDATE "PendingMfa"
        SET otp_hash = %s, expires_at = %s, attempts = 0, last_resend_at = %s
        WHERE token = %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(update_sql, (new_otp_hash, new_expires_at, now, token.strip()))
                return getattr(cursor, "rowcount", 0) > 0
        except Exception as e:
            logger.debug(f"Error updating pending password change OTP: {e}")
            return False

    def clear_pending_password_change(self, token: Optional[str]) -> None:
        """Deletes pending password change state from PostgreSQL."""
        if not token or not isinstance(token, str):
            return
        sql = 'DELETE FROM "PendingMfa" WHERE token = %s;'
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (token.strip(),))
        except Exception as e:
            logger.debug(f"Error clearing pending password change token: {e}")
