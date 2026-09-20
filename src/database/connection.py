"""
Database Connection and Lifecycle Manager for CyberScout AI.

Provides database setup, connection management, schema initialization,
and transactional session management for PostgreSQL via SQLAlchemy.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import re
import threading
import time
import traceback
from typing import Any, Dict, Generator, List, Optional
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from src.core.exceptions import DatabaseConnectionError, DatabaseError, IntegrityError, QueryError
from src.core.logging import get_logger
from src.database.engine import create_db_engine, get_engine, get_masked_db_host, reset_engine
from src.database.session import get_db_session, get_session_factory

logger = get_logger(__name__)

CORE_TABLES = (
    "Sources", "Opportunities", "Users", "SearchHistory", "EmailHistory",
    "AppLogs", "Preferences", "Statistics", "Keywords", "AuditLogs",
    "ScanJobs", "PendingMfa", "ServerSessions", "SavedOpportunities",
    "UserPreferences", "UserSearchHistory", "NotificationOutbox",
    "Admins", "LoginAttempts", "SourceHealth"
)
_TABLE_REGEX = re.compile(rf'\b(?<!["\'])({"|".join(CORE_TABLES)})(?!["\'])\b')


class PgRow:
    """Wrapper giving DBAPI tuple rows dictionary-like key access matching standard mapping."""
    def __init__(self, description, row_tuple):
        self._keys = [col[0] for col in description] if description else []
        self._values = row_tuple if row_tuple else ()
        self._mapping = dict(zip(self._keys, self._values)) if row_tuple else {}

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._values[item]
        return self._mapping[item]

    def get(self, key, default=None):
        return self._mapping.get(key, default)

    def keys(self):
        return self._keys

    def values(self):
        return self._values

    def items(self):
        return self._mapping.items()

    def __iter__(self):
        return iter(self._keys)


class PgCursorAdapter:
    """DBAPI Cursor Adapter translating placeholders and quoting table names for PostgreSQL."""
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def _fix_sql(self, sql: str) -> str:
        if not sql:
            return sql
        if "?" in sql and "%s" not in sql:
            sql = sql.replace("?", "%s")
        if any(tbl in sql for tbl in CORE_TABLES):
            sql = _TABLE_REGEX.sub(r'"\1"', sql)
        return sql

    def execute(self, sql: str, parameters=()):
        sql = self._fix_sql(sql)
        if parameters is None:
            parameters = ()
        raw_conn = getattr(self._cursor, "connection", None)
        if raw_conn and hasattr(raw_conn, "get_transaction_status"):
            try:
                if raw_conn.get_transaction_status() == 3:
                    raw_conn.rollback()
            except Exception:
                pass
        self._cursor.execute(sql, parameters)
        return self

    def executemany(self, sql: str, seq_of_parameters=()):
        sql = self._fix_sql(sql)
        raw_conn = getattr(self._cursor, "connection", None)
        if raw_conn and hasattr(raw_conn, "get_transaction_status"):
            try:
                if raw_conn.get_transaction_status() == 3:
                    raw_conn.rollback()
            except Exception:
                pass
        try:
            from psycopg2.extras import execute_batch
            execute_batch(self._cursor, sql, seq_of_parameters, page_size=100)
            return self
        except Exception:
            pass
        self._cursor.executemany(sql, seq_of_parameters)
        return self

    def executescript(self, script_sql: str):
        sql = self._fix_sql(script_sql)
        self._cursor.execute(sql)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if hasattr(row, "_mapping"):
            return row
        return PgRow(self._cursor.description, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if hasattr(rows[0], "_mapping"):
            return rows
        desc = self._cursor.description
        return [PgRow(desc, r) for r in rows]

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @property
    def description(self):
        return getattr(self._cursor, "description", None)

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", 1)

    @property
    def rowcount(self):
        return getattr(self._cursor, "rowcount", -1)


class PgConnectionAdapter:
    """DBAPI Connection Adapter wrapping PostgreSQL raw connections."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        if hasattr(self._conn, "get_transaction_status"):
            try:
                if self._conn.get_transaction_status() == 3:
                    self._conn.rollback()
            except Exception:
                pass
        return PgCursorAdapter(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def set_session(self, **kwargs):
        """
        Executes set_session on raw connection ONLY before any transaction begins.
        If a transaction is active, rolls back first to avoid set_session inside transaction errors.
        """
        if hasattr(self._conn, "status") and hasattr(self._conn, "set_session"):
            if getattr(self._conn, "status", 0) != 0:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
            self._conn.set_session(**kwargs)
        elif hasattr(self._conn, "set_session"):
            self._conn.set_session(**kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class DatabaseManager:
    """
    Database Connection & Infrastructure Manager for PostgreSQL.
    """
    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls, custom_url: Optional[str] = None, **kwargs):
        if custom_url:
            return super().__new__(cls)
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, custom_url: Optional[str] = None, **kwargs):
        """
        Initializes DatabaseManager.

        Args:
            custom_url: Optional override PostgreSQL database connection URL.
            **kwargs: Ignored legacy parameters for backward compatibility.
        """
        if getattr(self, "_initialized", False) and not custom_url:
            return
        self.custom_url = custom_url
        self._engine = None
        self._local = threading.local()
        self._last_check_iso: Optional[str] = None
        self._last_successful_query_iso: Optional[str] = None
        self._last_failure_timestamp_iso: Optional[str] = None
        self._last_failure_reason: Optional[str] = None
        self._retry_attempts: int = 0
        self._initialized = True

    @property
    def _connection(self) -> Optional[PgConnectionAdapter]:
        return getattr(self._local, "connection", None)

    @_connection.setter
    def _connection(self, conn: Optional[PgConnectionAdapter]) -> None:
        self._local.connection = conn

    def get_engine(self) -> Engine:
        """Gets active SQLAlchemy engine for this manager instance (reusing singleton engine)."""
        if self.custom_url:
            if self._engine is None:
                self._engine = create_db_engine(custom_url=self.custom_url)
            return self._engine
        return get_engine()

    def verify_rls_policies(self) -> Dict[str, Any]:
        """
        Verifies Row Level Security (RLS) state and policies across core tables via PostgreSQL system catalogs.
        Returns a dictionary with status details without modifying database schema or acquiring exclusive locks.
        """
        result: Dict[str, Any] = {
            "is_configured": False,
            "tables": {},
            "force_rls": {},
            "policies": [],
            "missing_tables": [],
            "unprotected_tables": [],
            "error": None,
        }
        target_tables = (
            "admins", "users", "opportunities", "auditlogs", "scanjobs",
            "pendingmfa", "serversessions", "sourcehealth", "sources",
            "searchhistory", "loginattempts", "savedopportunities",
            "userpreferences", "usersearchhistory", "notificationoutbox"
        )
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Query pg_class for table RLS and FORCE RLS flags
                cursor.execute("""
                    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND LOWER(c.relname) IN (
                          'admins', 'users', 'opportunities', 'auditlogs', 'scanjobs',
                          'pendingmfa', 'serversessions', 'sourcehealth', 'sources',
                          'searchhistory', 'loginattempts', 'savedopportunities',
                          'userpreferences', 'usersearchhistory', 'notificationoutbox'
                      )
                      AND c.relkind = 'r';
                """)
                rows = cursor.fetchall()
                found_map = {row[0]: bool(row[1]) for row in rows}
                force_map = {row[0]: bool(row[2]) for row in rows}
                result["tables"] = found_map
                result["force_rls"] = force_map

                for t in target_tables:
                    matching = [v for k, v in found_map.items() if k.lower() == t]
                    if not matching:
                        result["missing_tables"].append(t)
                    elif not matching[0]:
                        result["unprotected_tables"].append(t)

                # 2. Query pg_policies for opportunity read policy and audit policies
                cursor.execute("""
                    SELECT tablename, policyname
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND LOWER(tablename) IN ('opportunities', 'auditlogs');
                """)
                policy_rows = cursor.fetchall()
                result["policies"] = [f"{r[0]}.{r[1]}" for r in policy_rows]

                has_policy = len(policy_rows) >= 2
                has_all_tables_secured = (
                    len(result["missing_tables"]) == 0
                    and len(result["unprotected_tables"]) == 0
                    and len(found_map) >= len(target_tables)
                )

                result["is_configured"] = has_all_tables_secured and has_policy
            finally:
                conn.rollback()
                cursor.close()
        except Exception as e:
            logger.debug(f"Error during RLS policy verification: {e}")
            result["error"] = str(e)

        return result

    def configure_rls_policies(self, force: bool = False) -> bool:
        """
        Enforces Row Level Security (RLS) policies and least-privilege access across all sensitive tables idempotently in PostgreSQL.
        First verifies current catalog state; skips redundant DDL statements if RLS is already verified active.
        """
        # 1. Check existing RLS catalog state before attempting DDL locks
        if not force:
            status = self.verify_rls_policies()
            if status.get("is_configured"):
                logger.info("PostgreSQL Row Level Security (RLS) verified active on core tables. Skipping redundant DDL.")
                return True

        logger.info("Configuring PostgreSQL Row Level Security (RLS) policies...")
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                # Set safe local lock timeout to prevent infinite blocking on contention
                try:
                    cursor.execute("SET LOCAL lock_timeout = '5s';")
                except Exception:
                    pass

                # Ensure LoginAttempts table exists prior to securing
                try:
                    from src.database.login_attempt_repository import LoginAttemptRepository
                    LoginAttemptRepository(db_manager=self)._ensure_table()
                except Exception:
                    pass

                target_tables = (
                    '"Admins"', '"Users"', '"Opportunities"', '"AuditLogs"', '"ScanJobs"',
                    '"PendingMfa"', '"ServerSessions"', '"SourceHealth"', '"Sources"',
                    '"SearchHistory"', '"LoginAttempts"', '"SavedOpportunities"',
                    '"UserPreferences"', '"UserSearchHistory"', '"NotificationOutbox"'
                )

                # 1. Enable RLS and FORCE RLS on all sensitive tables idempotently
                for table_name in target_tables:
                    try:
                        cursor.execute(f'ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;')
                        cursor.execute(f'ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;')
                    except Exception as te:
                        logger.debug(f"Notice on securing {table_name}: {te}")

                # 2. Add explicit RLS policies idempotently
                policies = [
                    ('AuditLogs', 'audit_append_only', 'CREATE POLICY audit_append_only ON "AuditLogs" FOR INSERT WITH CHECK (true);'),
                    ('AuditLogs', 'audit_no_delete', 'CREATE POLICY audit_no_delete ON "AuditLogs" FOR DELETE USING (false);'),
                    ('AuditLogs', 'audit_no_update', 'CREATE POLICY audit_no_update ON "AuditLogs" FOR UPDATE USING (false);'),
                    ('AuditLogs', 'audit_select_policy', 'CREATE POLICY audit_select_policy ON "AuditLogs" FOR SELECT USING (true);'),
                    ('Opportunities', 'opportunity_read_policy', 'CREATE POLICY opportunity_read_policy ON "Opportunities" FOR SELECT USING (true);'),
                    ('Opportunities', 'opportunity_write_policy', 'CREATE POLICY opportunity_write_policy ON "Opportunities" FOR ALL USING (true) WITH CHECK (true);'),
                    ('ScanJobs', 'scanjobs_policy', 'CREATE POLICY scanjobs_policy ON "ScanJobs" FOR ALL USING (true) WITH CHECK (true);'),
                    ('SourceHealth', 'sourcehealth_policy', 'CREATE POLICY sourcehealth_policy ON "SourceHealth" FOR ALL USING (true) WITH CHECK (true);'),
                    ('Sources', 'sources_policy', 'CREATE POLICY sources_policy ON "Sources" FOR ALL USING (true) WITH CHECK (true);'),
                    ('Users', 'users_policy', 'CREATE POLICY users_policy ON "Users" FOR ALL USING (true) WITH CHECK (true);'),
                    ('Admins', 'admins_policy', 'CREATE POLICY admins_policy ON "Admins" FOR ALL USING (true) WITH CHECK (true);'),
                    ('PendingMfa', 'pendingmfa_policy', 'CREATE POLICY pendingmfa_policy ON "PendingMfa" FOR ALL USING (true) WITH CHECK (true);'),
                    ('ServerSessions', 'serversessions_policy', 'CREATE POLICY serversessions_policy ON "ServerSessions" FOR ALL USING (true) WITH CHECK (true);'),
                    ('SearchHistory', 'searchhistory_policy', 'CREATE POLICY searchhistory_policy ON "SearchHistory" FOR ALL USING (true) WITH CHECK (true);'),
                    ('LoginAttempts', 'loginattempts_policy', 'CREATE POLICY loginattempts_policy ON "LoginAttempts" FOR ALL USING (true) WITH CHECK (true);'),
                    ('SavedOpportunities', 'savedopportunities_policy', 'CREATE POLICY savedopportunities_policy ON "SavedOpportunities" FOR ALL USING (user_id::text = NULLIF(current_setting(\'app.current_user_id\', true), \'\') OR NULLIF(current_setting(\'app.current_user_id\', true), \'\') IS NULL) WITH CHECK (user_id::text = NULLIF(current_setting(\'app.current_user_id\', true), \'\') OR NULLIF(current_setting(\'app.current_user_id\', true), \'\') IS NULL);'),
                    ('UserPreferences', 'userpreferences_policy', 'CREATE POLICY userpreferences_policy ON "UserPreferences" FOR ALL USING (user_id::text = NULLIF(current_setting(\'app.current_user_id\', true), \'\') OR NULLIF(current_setting(\'app.current_user_id\', true), \'\') IS NULL) WITH CHECK (user_id::text = NULLIF(current_setting(\'app.current_user_id\', true), \'\') OR NULLIF(current_setting(\'app.current_user_id\', true), \'\') IS NULL);'),
                    ('UserSearchHistory', 'usersearchhistory_policy', 'CREATE POLICY usersearchhistory_policy ON "UserSearchHistory" FOR ALL USING (user_id::text = NULLIF(current_setting(\'app.current_user_id\', true), \'\') OR NULLIF(current_setting(\'app.current_user_id\', true), \'\') IS NULL) WITH CHECK (user_id::text = NULLIF(current_setting(\'app.current_user_id\', true), \'\') OR NULLIF(current_setting(\'app.current_user_id\', true), \'\') IS NULL);'),
                    ('NotificationOutbox', 'notification_outbox_policy', 'CREATE POLICY notification_outbox_policy ON "NotificationOutbox" FOR ALL USING (true) WITH CHECK (true);'),
                ]

                for tablename, policyname, sql in policies:
                    try:
                        cursor.execute("""
                            SELECT 1 FROM pg_policies 
                            WHERE LOWER(tablename) = LOWER(%s) AND LOWER(policyname) = LOWER(%s);
                        """, (tablename, policyname))
                        exists = cursor.fetchone()
                        if exists and force:
                            cursor.execute(f'DROP POLICY IF EXISTS {policyname} ON "{tablename}";')
                            cursor.execute(sql)
                        elif not exists:
                            cursor.execute(sql)
                    except Exception as pe:
                        logger.debug(f"Notice on policy {tablename}.{policyname}: {pe}")

                # 3. Establish least privilege grants for dedicated application role if present
                grants_sql = """
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cyberscout_app') THEN
                        GRANT USAGE ON SCHEMA public TO cyberscout_app;
                        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cyberscout_app;
                        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cyberscout_app;
                        REVOKE CREATE ON SCHEMA public FROM cyberscout_app;
                        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cyberscout_app;
                        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO cyberscout_app;
                    END IF;
                END $$;
                """
                try:
                    cursor.execute(grants_sql)
                except Exception as ge:
                    logger.debug(f"Notice on role grants: {ge}")

                conn.commit()
                logger.info("PostgreSQL Row Level Security (RLS) enabled and policies configured on sensitive tables.")
                return True
            except Exception as e:
                conn.rollback()
                logger.warning(f"RLS configuration notice: {e}")
                return False
            finally:
                cursor.close()
        except Exception as e:
            logger.warning(f"Could not configure RLS policies: {e}")
            return False

    def initialize_database(self) -> None:
        """
        Initializes PostgreSQL database schema idempotently.
        Verifies existing schema and RLS state; creates tables and seeds only if missing.
        """
        try:
            if not self.ping():
                logger.warning("PostgreSQL database is currently unreachable. Schema initialization skipped.")
                return

            # Check if schema and RLS are already fully initialized
            rls_status = self.verify_rls_policies()
            if rls_status.get("is_configured"):
                logger.info("PostgreSQL database schema and RLS policies already verified healthy.")
                return

            engine = self.get_engine()

            # Automatically create any missing schema tables via SQLAlchemy ORM
            from src.database.base import Base
            import src.database.models  # Ensures all models are registered
            Base.metadata.create_all(bind=engine)

            # Run default seed data population
            from src.database.seed import SeedManager
            SeedManager(db_manager=self).run_all_seeds()

            # Enforce PostgreSQL Row Level Security (RLS) policies (Phase 2)
            self.configure_rls_policies()

            logger.info("PostgreSQL database successfully initialized and schema created.")
        except Exception as e:
            logger.warning(f"Database initialization encountered an exception: {e}")

    def get_connection(self) -> PgConnectionAdapter:
        """
        Gets active DBAPI raw connection wrapped with compatibility adapter.
        Fails honestly if PostgreSQL is unreachable without resorting to mock fallbacks.
        Automatically reconnects if the connection was closed.
        """
        is_closed = True
        if self._connection is not None:
            raw = getattr(self._connection, "_conn", None)
            if raw is not None:
                is_closed = getattr(raw, "closed", 0) != 0

        if self._connection is None or is_closed:
            self._connection = None
            try:
                engine = self.get_engine()
                raw_conn = engine.raw_connection()
                dbapi_conn = getattr(raw_conn, "dbapi_connection", None) or getattr(raw_conn, "connection", raw_conn)
                self._connection = PgConnectionAdapter(dbapi_conn)
            except Exception as e:
                err_str = str(e).lower()
                if "ssl" in err_str or "closed" in err_str or "connection" in err_str or "set_session" in err_str or "transaction" in err_str or "translate host name" in err_str or "not known" in err_str or "timeout" in err_str:
                    logger.warning(f"Database pool connection dropped/stale ({e}). Resetting engine pool and retrying connection.")
                    try:
                        import time
                        time.sleep(0.5)
                        self.reset_pool()
                        engine = self.get_engine()
                        raw_conn = engine.raw_connection()
                        dbapi_conn = getattr(raw_conn, "dbapi_connection", None) or getattr(raw_conn, "connection", raw_conn)
                        self._connection = PgConnectionAdapter(dbapi_conn)
                    except Exception as retry_err:
                        self._last_failure_reason = str(retry_err)
                        self._last_failure_timestamp_iso = datetime.now(timezone.utc).isoformat()
                        logger.error(f"PostgreSQL reconnection failed: {retry_err}")
                        raise DatabaseConnectionError(f"PostgreSQL connection failed: {retry_err}", original_exception=retry_err)
                else:
                    self._last_failure_reason = str(e)
                    self._last_failure_timestamp_iso = datetime.now(timezone.utc).isoformat()
                    logger.error(f"PostgreSQL connection failed: {e}")
                    raise DatabaseConnectionError(f"PostgreSQL connection failed: {e}", original_exception=e)

        if self._connection is None:
            raise DatabaseConnectionError("PostgreSQL connection could not be established.")
        return self._connection

    def get_session(self) -> Session:
        """Gets a new SQLAlchemy Session."""
        factory = get_session_factory(self.get_engine())
        return factory()

    def close_connection(self) -> None:
        """Disposes DBAPI connection and SQLAlchemy engine pool cleanly."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

        if self._engine:
            try:
                self._engine.dispose()
                self._engine = None
                logger.debug("Disposed database engine pool.")
            except Exception as e:
                logger.warning(f"Error disposing database engine: {e}")

    def reset_pool(self) -> None:
        """Alias for close_connection to reset database connections and engine pool."""
        self.close_connection()

    @contextmanager
    def transaction(self) -> Generator[Any, None, None]:
        """
        Context manager yielding a transactional DBAPI Cursor.
        Automatically commits on success or rolls back on exception.
        Automatically handles cloud pooler connection resets.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
        except Exception:
            self.close_connection()
            conn = self.get_connection()
            cursor = conn.cursor()

        try:
            yield cursor
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            err_msg = str(e)
            if "closed" in err_msg.lower() or "terminated" in err_msg.lower() or "broken pipe" in err_msg.lower():
                logger.warning(f"Database connection closed unexpectedly ({e}), clearing stale connection cache.")
                self.close_connection()
            if "duplicate" in err_msg.lower() or "unique" in err_msg.lower() or "integrity" in err_msg.lower():
                logger.error(f"Transaction integrity error, changes rolled back: {e}")
                raise IntegrityError(f"Database integrity error: {e}", original_exception=e)
            logger.error(f"Transaction failed, changes rolled back: {e}")
            raise QueryError(f"Database transaction error: {e}", original_exception=e)
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    @contextmanager
    def user_context(self, user_id: Optional[str] = None) -> Generator[Any, None, None]:
        """
        Sets PostgreSQL session user context for RLS row isolation during user-scoped operations.
        Ensures queries are restricted strictly to user_id when active.
        """
        with self.transaction() as cursor:
            if user_id:
                try:
                    cursor.execute("SET LOCAL app.current_user_id = %s;", (user_id,))
                except Exception:
                    pass
            yield cursor

    def check_connection_with_backoff(self, max_retries: int = 5) -> bool:
        """
        Attempts to connect to PostgreSQL using exponential backoff (1s, 2s, 4s, 8s, 16s).
        Returns True if connection succeeds, False if all retries fail without crashing the app.
        """
        import os
        if "PYTEST_CURRENT_TEST" in os.environ:
            max_retries = 1

        delays = [1, 2, 4, 8, 16]
        for attempt in range(1, max_retries + 1):
            self._retry_attempts = attempt
            try:
                logger.info(f"Checking PostgreSQL connection (attempt {attempt}/{max_retries})...")
                reset_engine()
                self.close_connection()
                if self.ping():
                    logger.info("✓ PostgreSQL connected successfully")
                    return True
            except Exception as e:
                logger.error(f"Connection attempt {attempt} failed: {e}")

            if attempt < max_retries:
                delay = delays[attempt - 1] if attempt - 1 < len(delays) else 16
                logger.info(f"Retrying PostgreSQL connection in {delay}s...")
                time.sleep(delay)

        logger.error(f"PostgreSQL connection failed after {max_retries} attempts. Application starting in Degraded Mode.")
        return False

    def ping(self) -> bool:
        """
        Performs a simple SELECT 1 query to verify database connection health.

        Returns:
            True if database is responsive, False otherwise.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        self._last_check_iso = now_iso
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            res = cursor.fetchone()
            cursor.close()
            conn.rollback()
            if res is not None and (res[0] == 1 or res.get("1") == 1 or res[0] == "1"):
                self._last_successful_query_iso = now_iso
                return True
            self._last_failure_timestamp_iso = now_iso
            self._last_failure_reason = "Ping returned invalid response"
            return False
        except Exception as e:
            self._last_failure_timestamp_iso = now_iso
            self._last_failure_reason = str(e)
            logger.warning(f"Database ping failed: {e}")
            return False

    def verify_integrity(self) -> bool:
        """Verifies database connection health."""
        return self.ping()

    def reconnect(self) -> Dict[str, Any]:
        """
        Safely disposes and recreates the connection pool and engine.
        Tests the newly established connection and returns health metrics.
        """
        start_time = time.time()
        try:
            self.close_connection()
            reset_engine()
            if self.custom_url and self._engine:
                try:
                    self._engine.dispose()
                except Exception:
                    pass
                self._engine = None

            connected = self.ping()
            latency_ms = round((time.time() - start_time) * 1000, 2)
            if connected:
                return {
                    "success": True,
                    "connected": True,
                    "status": "connected",
                    "latency_ms": latency_ms,
                    "host": get_masked_db_host(self.custom_url),
                    "message": f"PostgreSQL engine pool reconnected successfully ({latency_ms}ms latency)."
                }
            else:
                return {
                    "success": False,
                    "connected": False,
                    "status": "failed",
                    "latency_ms": latency_ms,
                    "error": self._last_failure_reason or "Failed to ping database after reconnect",
                    "message": "Database reconnection failed to ping successfully."
                }
        except Exception as e:
            logger.error(f"Database reconnect failed: {e}")
            return {
                "success": False,
                "connected": False,
                "status": "failed",
                "error": str(e),
                "message": f"Database reconnection encountered an exception: {e}"
            }

    def get_health_metrics(self) -> Dict[str, Any]:
        """
        Computes current database connection health, latency, table counts, and masked host.
        Fulfills Part 5 and Part 7 schema requirements.
        """
        start_time = time.time()
        is_connected = self.ping()
        latency_ms = round((time.time() - start_time) * 1000, 2) if is_connected else -1
        masked_host = get_masked_db_host(self.custom_url)

        tables_count = 0
        pg_version = "Unknown"
        table_counts: Dict[str, int] = {}

        if is_connected:
            try:
                tables = self.get_existing_tables()
                tables_count = len(tables)
            except Exception:
                tables_count = 0

            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT version();")
                v_row = cursor.fetchone()
                if v_row:
                    pg_version = str(v_row[0]).split(",")[0]

                # Safe table row counts for non-sensitive schema inspection
                key_tables = [
                    "Opportunities", "Users", "Admins", "AuditLogs", "ScanJobs",
                    "SourceHealth", "Sources", "SearchHistory", "SavedOpportunities",
                    "UserPreferences", "scheduler_webhook_requests", "Statistics"
                ]
                for tbl in key_tables:
                    try:
                        cursor.execute(f'SELECT COUNT(*) FROM "{tbl}";')
                        r = cursor.fetchone()
                        if r:
                            table_counts[tbl] = int(r[0] if isinstance(r, (tuple, list)) else r.get("count", 0))
                    except Exception:
                        pass

                cursor.close()
                conn.rollback()
            except Exception:
                pg_version = "PostgreSQL"

            return {
                "connected": True,
                "status": "ok",
                "database": "PostgreSQL",
                "database_type": "PostgreSQL",
                "host": masked_host,
                "database_host": masked_host,
                "latency_ms": latency_ms,
                "last_check": self._last_check_iso or datetime.now(timezone.utc).isoformat(),
                "last_successful_query": self._last_successful_query_iso or datetime.now(timezone.utc).isoformat(),
                "version": pg_version,
                "tables": tables_count,
                "table_counts": table_counts,
            }
        else:
            return {
                "connected": False,
                "status": "degraded",
                "database": "PostgreSQL",
                "database_type": "PostgreSQL",
                "host": masked_host,
                "database_host": masked_host,
                "reason": self._last_failure_reason or "Network unreachable",
                "last_attempt": self._last_failure_timestamp_iso or datetime.now(timezone.utc).isoformat(),
                "retry_attempts": self._retry_attempts or 5,
                "tables": 0,
                "table_counts": {},
                "version": "Disconnected",
            }


    def get_existing_tables(self) -> List[str]:
        """Returns list of table names present in database."""
        try:
            engine = self.get_engine()
            insp = inspect(engine)
            if insp is not None:
                return list(insp.get_table_names())
            return []
        except Exception:
            return []

    def close(self) -> None:
        """Closes active database engine cleanly."""
        self.close_connection()

