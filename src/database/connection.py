"""
Database Connection and Lifecycle Manager for CyberScout AI.

Provides database setup, connection management, schema initialization,
and transactional session management for PostgreSQL via SQLAlchemy.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
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
        if "?" in sql and "%s" not in sql:
            sql = sql.replace("?", "%s")
        import re
        for tbl in ["Sources", "Opportunities", "Users", "SearchHistory", "EmailHistory", "AppLogs", "Preferences", "Statistics", "Keywords", "AuditLogs"]:
            sql = re.sub(rf'\b(?<!"){tbl}(?!")\b', f'"{tbl}"', sql)
        return sql

    def execute(self, sql: str, parameters=()):
        sql = self._fix_sql(sql)
        if parameters is None:
            parameters = ()
        self._cursor.execute(sql, parameters)
        return self

    def executemany(self, sql: str, seq_of_parameters=()):
        sql = self._fix_sql(sql)
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
        if hasattr(self._conn, "status") and getattr(self._conn, "status", 0) != 0:
            try:
                self._conn.rollback()
            except Exception:
                pass

    def cursor(self):
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

    def __init__(self, custom_url: Optional[str] = None, **kwargs):
        """
        Initializes DatabaseManager.

        Args:
            custom_url: Optional override PostgreSQL database connection URL.
            **kwargs: Ignored legacy parameters for backward compatibility.
        """
        self.custom_url = custom_url
        self._engine = None
        self._connection = None
        self._last_check_iso: Optional[str] = None
        self._last_successful_query_iso: Optional[str] = None
        self._last_failure_timestamp_iso: Optional[str] = None
        self._last_failure_reason: Optional[str] = None
        self._retry_attempts: int = 0

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
        result = {
            "is_configured": False,
            "tables": {},
            "policies": [],
            "missing_tables": [],
            "unprotected_tables": [],
        }
        target_tables = ("admins", "users", "opportunities", "auditlogs")
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Query pg_class for table RLS flags
                cursor.execute("""
                    SELECT c.relname, c.relrowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND LOWER(c.relname) IN ('admins', 'users', 'opportunities', 'auditlogs')
                      AND c.relkind = 'r';
                """)
                rows = cursor.fetchall()
                found_map = {row[0]: bool(row[1]) for row in rows}
                result["tables"] = found_map

                for t in target_tables:
                    matching = [v for k, v in found_map.items() if k.lower() == t]
                    if not matching:
                        result["missing_tables"].append(t)
                    elif not matching[0]:
                        result["unprotected_tables"].append(t)

                # 2. Query pg_policies for opportunity read policy
                cursor.execute("""
                    SELECT tablename, policyname
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND LOWER(tablename) = 'opportunities'
                      AND policyname = 'opportunity_read_policy';
                """)
                policy_rows = cursor.fetchall()
                result["policies"] = [f"{r[0]}.{r[1]}" for r in policy_rows]

                has_policy = len(policy_rows) > 0
                has_all_tables_secured = (
                    len(result["missing_tables"]) == 0
                    and len(result["unprotected_tables"]) == 0
                    and len(found_map) >= len(target_tables)
                )

                result["is_configured"] = bool(has_all_tables_secured and has_policy)
            finally:
                conn.rollback()
                cursor.close()
        except Exception as e:
            logger.debug(f"Error during RLS policy verification: {e}")
            result["error"] = str(e)

        return result

    def configure_rls_policies(self, force: bool = False) -> bool:
        """
        Enforces Row Level Security (RLS) policies across core tables idempotently in PostgreSQL.
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

                # 1. Enable RLS on core tables idempotently
                for table_name in ('"Admins"', '"Users"', '"Opportunities"', '"AuditLogs"'):
                    cursor.execute(f'ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;')

                # 2. Add explicit RLS policies idempotently
                rls_policy_sql = """
                DO $$
                BEGIN
                    -- Opportunities Read Policy for public/authenticated reads
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'Opportunities' AND policyname = 'opportunity_read_policy') THEN
                        CREATE POLICY opportunity_read_policy ON "Opportunities" FOR SELECT USING (true);
                    END IF;
                END $$;
                """
                cursor.execute(rls_policy_sql)
                conn.commit()
                logger.info("PostgreSQL Row Level Security (RLS) enabled and policies configured on core tables.")
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
                if "ssl" in err_str or "closed" in err_str or "connection" in err_str or "set_session" in err_str or "transaction" in err_str:
                    logger.warning(f"Database pool connection dropped/stale ({e}). Resetting engine pool and retrying connection.")
                    try:
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
                cursor.close()
                conn.rollback()
                if v_row:
                    pg_version = str(v_row[0]).split(",")[0]
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

