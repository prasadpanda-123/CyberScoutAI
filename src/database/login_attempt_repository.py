"""
Login Attempt Repository for CyberScout AI.

Provides distributed, database-backed failed login attempt tracking and account lockout
protection across multiple server workers (SEC-07, SEC-11).
Replaces vulnerable process-local in-memory state with PostgreSQL persistence.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from src.database.connection import DatabaseManager
from src.core.logging import get_logger

logger = get_logger(__name__)


class LoginAttemptRepository:
    """
    Database-backed distributed rate limiter and lockout manager.
    Tracks failed authentication attempts across multiple worker processes.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._table_initialized = False
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Idempotently creates the LoginAttempts table and performance indexes."""
        if self._table_initialized:
            return
        sql = """
        CREATE TABLE IF NOT EXISTS "LoginAttempts" (
            id SERIAL PRIMARY KEY,
            ip_address VARCHAR(64) NOT NULL,
            identifier VARCHAR(255) NOT NULL,
            attempt_type VARCHAR(32) NOT NULL DEFAULT 'admin_login',
            attempted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup 
        ON "LoginAttempts" (ip_address, identifier, attempted_at);
        CREATE INDEX IF NOT EXISTS idx_login_attempts_type 
        ON "LoginAttempts" (attempt_type, attempted_at);
        """
        initialized = False
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                # Handle SQLite vs PostgreSQL SERIAL syntax if in test mode
                if getattr(self.db_manager, "is_sqlite", False):
                    sqlite_ddl = """
                    CREATE TABLE IF NOT EXISTS "LoginAttempts" (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address VARCHAR(64) NOT NULL,
                        identifier VARCHAR(255) NOT NULL,
                        attempt_type VARCHAR(32) NOT NULL DEFAULT 'admin_login',
                        attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup 
                    ON "LoginAttempts" (ip_address, identifier, attempted_at);
                    """
                    cursor.executescript(sqlite_ddl)
                else:
                    cursor.execute(sql)
                conn.commit()
                self._table_initialized = True
                initialized = True
            except Exception as e:
                conn.rollback()
                logger.debug(f"LoginAttempts table initialization notice: {e}")
            finally:
                cursor.close()
        except Exception as e:
            logger.debug(f"Could not initialize LoginAttempts table: {e}")
        if initialized:
            # Keep the distributed throttle table bounded across long-lived Render instances.
            self.prune_old_attempts(max_age_minutes=24 * 60)

    def record_failed_attempt(
        self,
        ip_address: str,
        identifier: str,
        attempt_type: str = "admin_login",
    ) -> None:
        """
        Records a failed login attempt for the given IP, identifier, and attempt type.
        """
        clean_ip = (ip_address or "unknown").strip()[:64]
        clean_id = (identifier or "").strip().lower()[:255]
        clean_type = (attempt_type or "admin_login").strip()[:32]
        now = datetime.now(timezone.utc)

        sql = """
        INSERT INTO "LoginAttempts" (ip_address, identifier, attempt_type, attempted_at)
        VALUES (%s, %s, %s, %s);
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (clean_ip, clean_id, clean_type, now))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.warning(f"Failed to record failed login attempt in database: {e}")
            finally:
                cursor.close()
        except Exception as e:
            logger.warning(f"Database connection error recording failed login attempt: {e}")

    def get_failed_attempts_count(
        self,
        ip_address: str,
        identifier: str,
        attempt_type: str = "admin_login",
        window_minutes: int = 15,
    ) -> int:
        """
        Returns count of failed login attempts for target within the active window.
        """
        clean_ip = (ip_address or "unknown").strip()[:64]
        clean_id = (identifier or "").strip().lower()[:255]
        clean_type = (attempt_type or "admin_login").strip()[:32]
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        sql = """
        SELECT COUNT(*) FROM "LoginAttempts"
        WHERE ip_address = %s
          AND identifier = %s
          AND attempt_type = %s
          AND attempted_at >= %s;
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (clean_ip, clean_id, clean_type, cutoff))
                row = cursor.fetchone()
                return int(row[0]) if row else 0
            except Exception as e:
                logger.warning(f"Failed to query login attempts count: {e}")
                raise RuntimeError("Login attempt state is unavailable; authentication must fail closed.") from e
            finally:
                cursor.close()
        except Exception as e:
            logger.warning(f"Database connection error checking login attempts: {e}")
            raise RuntimeError("Login attempt state is unavailable; authentication must fail closed.") from e

    def check_and_record_rate_limit(
        self,
        ip_address: str,
        identifier: str,
        attempt_type: str,
        *,
        max_attempts: int,
        window_minutes: int,
    ) -> bool:
        """Atomically records a request if its shared PostgreSQL rate-limit bucket allows it."""
        self._ensure_table()
        if not self._table_initialized:
            raise RuntimeError("Distributed rate-limit storage is unavailable.")

        clean_ip = (ip_address or "unknown").strip()[:64]
        clean_id = (identifier or "").strip().lower()[:255]
        clean_type = (attempt_type or "request").strip()[:32]
        try:
            with self.db_manager.transaction() as cursor:
                # Serialize requests within a bucket so concurrent workers cannot race the count.
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s));",
                    (f"{clean_type}:{clean_ip}", clean_id),
                )
                cursor.execute(
                    """SELECT COUNT(*) FROM "LoginAttempts"
                       WHERE ip_address = %s AND identifier = %s AND attempt_type = %s
                         AND attempted_at >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 minute');""",
                    (clean_ip, clean_id, clean_type, int(window_minutes)),
                )
                row = cursor.fetchone()
                count = int(row[0]) if row else 0
                if count >= max_attempts:
                    return False
                cursor.execute(
                    """INSERT INTO "LoginAttempts" (ip_address, identifier, attempt_type, attempted_at)
                       VALUES (%s, %s, %s, CURRENT_TIMESTAMP);""",
                    (clean_ip, clean_id, clean_type),
                )
            return True
        except Exception as exc:
            logger.error(f"Distributed rate-limit check failed for {clean_type}: {exc}")
            raise RuntimeError("Distributed rate-limit storage is unavailable.") from exc

    def is_locked_out(
        self,
        ip_address: str,
        identifier: str,
        attempt_type: str = "admin_login",
        max_attempts: int = 5,
        window_minutes: int = 15,
    ) -> bool:
        """
        Determines whether the given IP / identifier is locked out.
        """
        count = self.get_failed_attempts_count(
            ip_address=ip_address,
            identifier=identifier,
            attempt_type=attempt_type,
            window_minutes=window_minutes,
        )
        return count >= max_attempts

    def reset_failed_attempts(
        self,
        ip_address: str,
        identifier: str,
        attempt_type: str = "admin_login",
    ) -> None:
        """
        Resets failed attempt records upon successful authentication.
        """
        clean_ip = (ip_address or "unknown").strip()[:64]
        clean_id = (identifier or "").strip().lower()[:255]
        clean_type = (attempt_type or "admin_login").strip()[:32]

        sql = """
        DELETE FROM "LoginAttempts"
        WHERE ip_address = %s
          AND identifier = %s
          AND attempt_type = %s;
        """
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (clean_ip, clean_id, clean_type))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.warning(f"Failed to reset login attempts: {e}")
            finally:
                cursor.close()
        except Exception as e:
            logger.warning(f"Database connection error resetting login attempts: {e}")

    def prune_old_attempts(self, max_age_minutes: int = 60) -> int:
        """
        Prunes expired login attempt records older than max_age_minutes.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        sql = 'DELETE FROM "LoginAttempts" WHERE attempted_at < %s;'
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (cutoff,))
                deleted = cursor.rowcount
                conn.commit()
                return deleted if deleted is not None else 0
            except Exception as e:
                conn.rollback()
                logger.warning(f"Failed to prune old login attempts: {e}")
                return 0
            finally:
                cursor.close()
        except Exception as e:
            logger.warning(f"Database connection error pruning login attempts: {e}")
            return 0
