"""Persistent, single-use password reset token storage."""

import hashlib
from typing import Any, Optional

from src.core.exceptions import RepositoryError
from src.database.connection import DatabaseManager


def hash_password_reset_token(raw_token: str) -> str:
    """Hashes a reset token before it is stored or queried."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class PasswordResetRepository:
    """Stores only hashed reset tokens and completes resets transactionally."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._table_ready = False

    def _ensure_table(self) -> None:
        if self._table_ready:
            return

        with self.db_manager.transaction() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PasswordResetTokens" (
                    token_hash CHAR(64) PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES "Users"(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    consumed_at TIMESTAMP WITH TIME ZONE NULL
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user
                ON "PasswordResetTokens"(user_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_expiry
                ON "PasswordResetTokens"(expires_at);
            """)
            cursor.execute('REVOKE ALL ON TABLE "PasswordResetTokens" FROM PUBLIC;')
            cursor.execute("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                        EXECUTE 'REVOKE ALL ON TABLE "PasswordResetTokens" FROM anon';
                    END IF;
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                        EXECUTE 'REVOKE ALL ON TABLE "PasswordResetTokens" FROM authenticated';
                    END IF;
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                        EXECUTE 'GRANT ALL ON TABLE "PasswordResetTokens" TO service_role';
                    END IF;
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cyberscout_app') THEN
                        EXECUTE 'GRANT ALL ON TABLE "PasswordResetTokens" TO cyberscout_app';
                    END IF;
                END $$;
            """)
        self._table_ready = True

    def store_token(self, user_id: str, raw_token: str) -> None:
        if not user_id or not raw_token:
            raise ValueError("A user identifier and reset token are required.")

        self._ensure_table()
        token_hash = hash_password_reset_token(raw_token)
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    'DELETE FROM "PasswordResetTokens" '
                    'WHERE expires_at <= CURRENT_TIMESTAMP OR consumed_at IS NOT NULL;'
                )
                cursor.execute("""
                    INSERT INTO "PasswordResetTokens" (token_hash, user_id, expires_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '1 hour');
                """, (token_hash, user_id))
        except Exception as exc:
            raise RepositoryError("Could not store password reset token.", original_exception=exc) from exc

    def get_valid_token(self, raw_token: str) -> Optional[dict[str, Any]]:
        if not isinstance(raw_token, str) or not raw_token:
            return None

        self._ensure_table()
        token_hash = hash_password_reset_token(raw_token)
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute("""
                    SELECT user_id
                    FROM "PasswordResetTokens"
                    WHERE token_hash = %s
                      AND consumed_at IS NULL
                      AND expires_at > CURRENT_TIMESTAMP;
                """, (token_hash,))
                row = cursor.fetchone()
                if not row:
                    return None
                user_id = self._get_user_id(row)
                return {"user_id": str(user_id)} if user_id else None
        except Exception as exc:
            raise RepositoryError("Could not verify password reset token.", original_exception=exc) from exc

    def complete_password_reset(self, raw_token: str, password_hash: str) -> Optional[str]:
        if not isinstance(raw_token, str) or not raw_token or not password_hash:
            return None

        self._ensure_table()
        token_hash = hash_password_reset_token(raw_token)
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute("""
                    UPDATE "PasswordResetTokens"
                    SET consumed_at = CURRENT_TIMESTAMP
                    WHERE token_hash = %s
                      AND consumed_at IS NULL
                      AND expires_at > CURRENT_TIMESTAMP
                    RETURNING user_id;
                """, (token_hash,))
                row = cursor.fetchone()
                if not row:
                    return None
                user_id = self._get_user_id(row)
                if not user_id:
                    raise RepositoryError("Password reset token has no associated account.")

                cursor.execute(
                    'UPDATE "Users" SET password_hash = %s WHERE id = %s;',
                    (password_hash, user_id),
                )
                if cursor.rowcount != 1:
                    raise RepositoryError("Password reset account no longer exists.")

                # A successful reset invalidates every other outstanding link for this user.
                cursor.execute("""
                    UPDATE "PasswordResetTokens"
                    SET consumed_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND consumed_at IS NULL;
                """, (user_id,))

                cursor.execute("""
                    UPDATE "ServerSessions"
                    SET revoked_at = CURRENT_TIMESTAMP
                    WHERE account_id = %s
                      AND account_type = 'user'
                      AND revoked_at IS NULL;
                """, (str(user_id),))
                return str(user_id)
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError("Could not complete password reset.", original_exception=exc) from exc

    @staticmethod
    def _get_user_id(row: Any) -> Any:
        try:
            return row["user_id"]
        except (KeyError, TypeError, IndexError):
            try:
                return row[0]
            except (KeyError, TypeError, IndexError):
                return getattr(row, "user_id", None)
