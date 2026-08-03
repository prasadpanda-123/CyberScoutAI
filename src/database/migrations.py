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
