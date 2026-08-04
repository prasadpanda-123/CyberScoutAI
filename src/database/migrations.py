"""
Database Migration Manager for CyberScout AI.

Manages schema versions, migration history, and sequential upgrades.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.database.connection import DatabaseManager
from src.core.exceptions import MigrationError
from src.core.logging import get_logger

logger = get_logger(__name__)


class Migration:
    """Represents a single database migration definition."""

    def __init__(self, version: int, description: str, sql: str):
        self.version = version
        self.description = description
        self.sql = sql


# Registry of system migrations
MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        description="Initial baseline schema creation",
        sql="""
        -- Baseline schema is initialized by DatabaseManager._create_schema
        SELECT 1;
        """,
    ),
    Migration(
        version=2,
        description="Knowledge Base & Historical Intelligence Schema v2",
        sql="""
        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id TEXT PRIMARY KEY,
            snapshot_date TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS provider_statistics (
            provider_name TEXT PRIMARY KEY,
            total_opportunities INTEGER DEFAULT 0,
            active_opportunities INTEGER DEFAULT 0,
            average_score REAL DEFAULT 0.0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS opportunity_history (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS retention_logs (
            id TEXT PRIMARY KEY,
            action_taken TEXT NOT NULL,
            records_affected INTEGER DEFAULT 0,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ),
    Migration(
        version=3,
        description="Phase 11.5 Quality Intelligence Schema Extension",
        sql="""
        SELECT 1;
        """,
    ),
    Migration(
        version=4,
        description="Phase 12 Production Data Intelligence Schema Extension",
        sql="""
        CREATE TABLE IF NOT EXISTS trend_statistics (
            id TEXT PRIMARY KEY,
            window_days INTEGER DEFAULT 30,
            metric_category TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            metric_value INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS historical_changes (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS link_validation (
            url TEXT PRIMARY KEY,
            status_code INTEGER DEFAULT 200,
            ssl_valid INTEGER DEFAULT 1,
            content_type TEXT,
            response_time REAL DEFAULT 0.0,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS quality_metrics_daily (
            date DATE PRIMARY KEY,
            total_collected INTEGER DEFAULT 0,
            total_accepted INTEGER DEFAULT 0,
            total_rejected INTEGER DEFAULT 0,
            total_duplicates INTEGER DEFAULT 0,
            total_expired INTEGER DEFAULT 0,
            avg_confidence REAL DEFAULT 0.0,
            avg_quality REAL DEFAULT 0.0,
            avg_freshness REAL DEFAULT 100.0
        );
        """,
    ),
]


QUALITY_COLUMNS = [
    ("confidence_score", "REAL DEFAULT 0.0"),
    ("quality_score", "REAL DEFAULT 0.0"),
    ("is_rejected", "INTEGER DEFAULT 0"),
    ("rejection_reason", "TEXT DEFAULT ''"),
    ("quality_flags", "TEXT DEFAULT ''"),
    ("topic_score", "REAL DEFAULT 0.0"),
    ("keyword_score", "REAL DEFAULT 0.0"),
    ("spam_score", "REAL DEFAULT 0.0"),
]

PRODUCTION_COLUMNS = [
    ("freshness_score", "REAL DEFAULT 100.0"),
    ("provider_score", "REAL DEFAULT 100.0"),
    ("link_status", "TEXT DEFAULT 'valid'"),
    ("verification_status", "TEXT DEFAULT 'verified'"),
    ("last_verified", "TIMESTAMP"),
    ("expired", "INTEGER DEFAULT 0"),
    ("archived", "INTEGER DEFAULT 0"),
]


class MigrationManager:
    """
    Tracks and executes database schema migrations.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def get_current_version(self) -> int:
        """Returns highest applied schema version, or 0 if uninitialized."""
        sql = "SELECT MAX(version) as current_version FROM schema_version;"
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()
            if row and row["current_version"] is not None:
                return row["current_version"]
            return 0
        except Exception:
            return 0

    def _get_existing_columns(self, table_name: str) -> List[str]:
        """Returns list of existing column names in a table."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name});")
            return [row[1] for row in cursor.fetchall()]
        except Exception:
            return []
        finally:
            cursor.close()

    def _apply_v3_quality_columns(self) -> None:
        """Safely adds Phase 11.5 quality columns if they don't exist."""
        existing = self._get_existing_columns("Opportunities")
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            for col_name, col_def in QUALITY_COLUMNS:
                if col_name not in existing:
                    cursor.execute(f"ALTER TABLE Opportunities ADD COLUMN {col_name} {col_def};")
                    logger.info(f"Added column '{col_name}' to Opportunities table.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to add quality columns: {e}", original_exception=e)
        finally:
            cursor.close()

    def _apply_v4_production_columns(self) -> None:
        """Safely adds Phase 12 production columns if they don't exist."""
        existing = self._get_existing_columns("Opportunities")
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            for col_name, col_def in PRODUCTION_COLUMNS:
                if col_name not in existing:
                    cursor.execute(f"ALTER TABLE Opportunities ADD COLUMN {col_name} {col_def};")
                    logger.info(f"Added column '{col_name}' to Opportunities table.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to add production columns: {e}", original_exception=e)
        finally:
            cursor.close()

    def apply_migrations(self) -> int:
        """
        Applies any pending migrations in sequential order.

        Returns:
            Number of newly applied migrations.
        """
        current_version = self.get_current_version()
        applied_count = 0

        for migration in MIGRATIONS:
            if migration.version > current_version:
                logger.info(f"Applying migration v{migration.version}: {migration.description}...")
                try:
                    now = datetime.now(timezone.utc).isoformat()

                    # Custom migration logic for v3 and v4
                    if migration.version == 3:
                        self._apply_v3_quality_columns()
                    elif migration.version == 4:
                        self._apply_v4_production_columns()

                    with self.db_manager.transaction() as cursor:
                        cursor.executescript(migration.sql)
                        cursor.execute(
                            "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?);",
                            (migration.version, now, migration.description),
                        )
                    applied_count += 1
                    logger.info(f"Successfully applied migration v{migration.version}.")
                except Exception as e:
                    raise MigrationError(f"Migration v{migration.version} failed: {e}", original_exception=e)

        return applied_count
