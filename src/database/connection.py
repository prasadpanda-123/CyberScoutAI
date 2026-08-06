"""
SQLite Database Connection and Schema Lifecycle Manager.

Handles connecting to SQLite, setting pragmas (WAL, foreign keys), creating
tables and indexes according to docs/architecture/sqlite_schema.md, health verification,
and clean setup/teardown.
"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator, List, Optional

from src.core.constants import DATA_DIR, DEFAULT_DB_NAME
from src.core.exceptions import DatabaseConnectionError, DatabaseError, IntegrityError, QueryError
from src.core.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    SQLite Connection & Infrastructure Manager.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initializes DatabaseManager with target SQLite database path.

        Args:
            db_path: Path to database file. Defaults to DATA_DIR/cyberscout.db.
        """
        self.db_path = db_path or (DATA_DIR / DEFAULT_DB_NAME)
        self._connection: Optional[sqlite3.Connection] = None

    def initialize_database(self) -> None:
        """
        Ensures target directory exists, establishes connection, enables PRAGMAs,
        and initializes the database schema if tables do not exist.
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = self.get_connection()
            self._create_schema(conn)
            from src.database.migrations import MigrationManager
            MigrationManager(db_manager=self).apply_migrations()
            from src.database.seed import SeedManager
            SeedManager(db_manager=self).run_all_seeds()
            logger.info(f"Database successfully initialized at '{self.db_path}'.")
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"Failed to initialize SQLite database at '{self.db_path}': {e}", original_exception=e)

    def get_connection(self) -> sqlite3.Connection:
        """
        Gets or creates an active SQLite connection with WAL mode and Foreign Keys enabled.

        Returns:
            Active sqlite3.Connection object.
        """
        if self._connection is None:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._connection = sqlite3.connect(
                    str(self.db_path),
                    check_same_thread=False,
                    timeout=20.0
                )
                self._connection.row_factory = sqlite3.Row
                # Configure PRAGMAs for concurrency and integrity
                cursor = self._connection.cursor()
                cursor.execute("PRAGMA foreign_keys = ON;")
                cursor.execute("PRAGMA journal_mode = WAL;")
                cursor.close()
                logger.debug(f"Connected to SQLite database: {self.db_path}")
            except sqlite3.Error as e:
                raise DatabaseConnectionError(f"Failed to connect to database '{self.db_path}': {e}", original_exception=e)
        return self._connection

    def close_connection(self) -> None:
        """Closes the active SQLite connection if open."""
        if self._connection:
            try:
                self._connection.close()
                self._connection = None
                logger.debug(f"Closed connection to database: {self.db_path}")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {e}")

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for transactional database operations.
        Automatically commits on success or rolls back on exception.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.rollback()
            logger.error(f"Transaction integrity error, changes rolled back: {e}")
            raise IntegrityError(f"Database integrity error: {e}", original_exception=e)
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed, changes rolled back: {e}")
            raise QueryError(f"Database transaction error: {e}", original_exception=e)
        finally:
            cursor.close()

    def ping(self) -> bool:
        """
        Performs a simple query to verify database connection health.

        Returns:
            True if database is responsive, False otherwise.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            cursor.close()
            return result is not None and result[0] == 1
        except Exception as e:
            logger.warning(f"Database ping failed: {e}")
            return False

    def verify_integrity(self) -> bool:
        """
        Runs SQLite PRAGMA quick_check to verify database file health.

        Returns:
            True if database passes integrity check, False otherwise.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check;")
            row = cursor.fetchone()
            cursor.close()
            return row is not None and row[0] == "ok"
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False

    def get_existing_tables(self) -> List[str]:
        """Returns list of table names present in the database."""
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [row["name"] for row in rows]
        finally:
            cursor.close()

    def close(self) -> None:
        """Closes active database connection cleanly."""
        if self._connection:
            try:
                self._connection.close()
                logger.debug("SQLite database connection closed.")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._connection = None

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """
        Creates SQLite tables and indexes matching sqlite_schema.md contract.
        """
        schema_sql = """
        -- 1. Opportunities Table
        CREATE TABLE IF NOT EXISTS Opportunities (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT NOT NULL,
            url_hash TEXT NOT NULL,
            source_id TEXT NOT NULL,
            category TEXT NOT NULL,
            provider TEXT,
            company TEXT,
            location TEXT,
            remote BOOLEAN DEFAULT 0,
            paid BOOLEAN,
            certificate BOOLEAN DEFAULT 0,
            price_raw TEXT,
            price_normalized TEXT,
            currency TEXT,
            deadline DATE,
            published_date DATE,
            discovered_date DATE NOT NULL,
            duration TEXT,
            difficulty TEXT DEFAULT 'unknown',
            tags TEXT,
            beginner_friendly BOOLEAN,
            score INTEGER DEFAULT 0,
            score_breakdown TEXT,
            confidence_score REAL DEFAULT 0.0,
            quality_score REAL DEFAULT 0.0,
            is_rejected BOOLEAN DEFAULT 0,
            rejection_reason TEXT,
            quality_flags TEXT,
            topic_score REAL DEFAULT 0.0,
            keyword_score REAL DEFAULT 0.0,
            spam_score REAL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'active',
            duplicate_of_id TEXT,
            run_id TEXT,
            raw_data TEXT,
            last_seen TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES Sources(id),
            FOREIGN KEY (duplicate_of_id) REFERENCES Opportunities(id),
            FOREIGN KEY (run_id) REFERENCES SearchHistory(run_id)
        );

        -- 2. Sources Table
        CREATE TABLE IF NOT EXISTS Sources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            collection_method TEXT NOT NULL,
            default_category TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            enabled BOOLEAN DEFAULT 1,
            official BOOLEAN DEFAULT 0,
            trust_score REAL DEFAULT 1.0,
            maintenance_level TEXT,
            update_frequency TEXT,
            max_requests_per_run INTEGER,
            request_delay_ms INTEGER
        );

        -- 3. Keywords Table
        CREATE TABLE IF NOT EXISTS Keywords (
            id TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            domain TEXT,
            synonym_of TEXT,
            FOREIGN KEY (synonym_of) REFERENCES Keywords(id)
        );

        -- 4. EmailHistory Table
        CREATE TABLE IF NOT EXISTS EmailHistory (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL,
            email_run_id TEXT NOT NULL,
            sent_at TIMESTAMP NOT NULL,
            clicked BOOLEAN DEFAULT 0,
            FOREIGN KEY (opportunity_id) REFERENCES Opportunities(id)
        );

        -- 5. SearchHistory Table
        CREATE TABLE IF NOT EXISTS SearchHistory (
            run_id TEXT PRIMARY KEY,
            triggered_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            status TEXT NOT NULL,
            sources_run TEXT,
            items_collected INTEGER DEFAULT 0,
            items_after_dedup INTEGER DEFAULT 0,
            items_emailed INTEGER DEFAULT 0,
            errors TEXT
        );

        -- 6. Statistics Table
        CREATE TABLE IF NOT EXISTS Statistics (
            id TEXT PRIMARY KEY,
            date DATE NOT NULL,
            source_id TEXT,
            category TEXT,
            count INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0.0,
            FOREIGN KEY (source_id) REFERENCES Sources(id)
        );

        -- 7. Preferences Table
        CREATE TABLE IF NOT EXISTS Preferences (
            id TEXT PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );

        -- 8. Schema Version Table (for Migrations)
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL,
            description TEXT
        );

        -- 9. Scheduler State Table (for Daily Email Delivery & Restart Safety)
        CREATE TABLE IF NOT EXISTS scheduler_state (
            id INTEGER PRIMARY KEY DEFAULT 1,
            last_email_sent TEXT,
            last_pipeline_run TEXT,
            updated_at TEXT
        );

        -- 10. Structured Persistent AppLogs Table
        CREATE TABLE IF NOT EXISTS AppLogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            level TEXT NOT NULL,
            module TEXT NOT NULL,
            function_name TEXT,
            message TEXT NOT NULL,
            execution_time_ms REAL,
            exception_text TEXT,
            correlation_id TEXT
        );

        -- 11. User Authentication & RBAC Table
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Viewer',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        -- 12. Security Audit Logs Table
        CREATE TABLE IF NOT EXISTS AuditLogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            username TEXT,
            event_type TEXT NOT NULL,
            action TEXT NOT NULL,
            source_ip TEXT,
            status TEXT NOT NULL,
            details TEXT
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_opportunities_url_hash ON Opportunities(url_hash);
        CREATE INDEX IF NOT EXISTS idx_opportunities_status ON Opportunities(status);
        CREATE INDEX IF NOT EXISTS idx_opportunities_score ON Opportunities(score);
        CREATE INDEX IF NOT EXISTS idx_opportunities_discovered_date ON Opportunities(discovered_date);
        CREATE INDEX IF NOT EXISTS idx_opportunities_deadline ON Opportunities(deadline);
        CREATE INDEX IF NOT EXISTS idx_opportunities_category ON Opportunities(category);
        CREATE INDEX IF NOT EXISTS idx_searchhistory_triggered_at ON SearchHistory(triggered_at);
        CREATE INDEX IF NOT EXISTS idx_emailhistory_opportunity_id ON EmailHistory(opportunity_id);
        CREATE INDEX IF NOT EXISTS idx_applogs_timestamp ON AppLogs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_applogs_level ON AppLogs(level);
        CREATE INDEX IF NOT EXISTS idx_applogs_module ON AppLogs(module);
        CREATE INDEX IF NOT EXISTS idx_users_email ON Users(email);
        CREATE INDEX IF NOT EXISTS idx_users_username ON Users(username);
        CREATE INDEX IF NOT EXISTS idx_auditlogs_timestamp ON AuditLogs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_auditlogs_event_type ON AuditLogs(event_type);
        """
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        cursor.close()
