"""
Regression Unit Tests for Migration Bootstrap System (Phase 12.2).
"""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.core.bootstrap import CyberScoutApp
from src.database.connection import DatabaseManager
from src.database.migrations import MIGRATIONS, MigrationManager


class TestMigrationBootstrap(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_bootstrap.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_empty_database_migration_bootstrap(self):
        """Verify that running MigrationManager on a completely empty database creates schema_version and applies all migrations."""
        db_mgr = DatabaseManager(db_path=self.db_path)
        mig_mgr = MigrationManager(db_mgr)

        # Database file doesn't exist yet
        self.assertFalse(self.db_path.exists())

        # Apply migrations directly on fresh DB
        applied = mig_mgr.apply_migrations()

        self.assertEqual(applied, len(MIGRATIONS))
        self.assertEqual(mig_mgr.get_current_version(), len(MIGRATIONS))

        # Check schema_version table exists and has entries
        conn = db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version, description FROM schema_version ORDER BY version ASC;")
        rows = cursor.fetchall()
        cursor.close()
        db_mgr.close()

        self.assertEqual(len(rows), len(MIGRATIONS))
        self.assertEqual(rows[0]["version"], 1)

    def test_existing_up_to_date_database(self):
        """Verify that running MigrationManager on an already migrated database applies 0 migrations cleanly."""
        db_mgr = DatabaseManager(db_path=self.db_path)
        mig_mgr = MigrationManager(db_mgr)
        applied_first = mig_mgr.apply_migrations()
        self.assertEqual(applied_first, len(MIGRATIONS))

        # Run again on existing database
        applied_second = mig_mgr.apply_migrations()
        self.assertEqual(applied_second, 0)
        self.assertEqual(mig_mgr.get_current_version(), len(MIGRATIONS))
        db_mgr.close()

    def test_partially_migrated_database(self):
        """Verify that a partially migrated database (e.g. version 2) correctly applies pending migrations (v3, v4)."""
        db_mgr = DatabaseManager(db_path=self.db_path)
        conn = db_mgr.get_connection()
        cursor = conn.cursor()

        # Manually create schema_version and insert v1 and v2 records
        cursor.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL,
                description TEXT
            );
        """)
        cursor.execute("INSERT INTO schema_version VALUES (1, '2026-01-01T00:00:00Z', 'v1 baseline');")
        cursor.execute("INSERT INTO schema_version VALUES (2, '2026-01-01T00:00:00Z', 'v2 schema');")
        conn.commit()
        cursor.close()

        mig_mgr = MigrationManager(db_mgr)
        self.assertEqual(mig_mgr.get_current_version(), 2)

        # Apply pending migrations
        applied = mig_mgr.apply_migrations()
        self.assertEqual(applied, len(MIGRATIONS) - 2)
        self.assertEqual(mig_mgr.get_current_version(), len(MIGRATIONS))
        db_mgr.close()

    def test_multiple_startup_executions_idempotency(self):
        """Verify that running CyberScoutApp startup twice in sequence on the same DB works without exceptions."""
        db_mgr = DatabaseManager(db_path=self.db_path)
        
        # First initialization
        db_mgr.initialize_database()
        tables_first = db_mgr.get_existing_tables()
        self.assertIn("schema_version", tables_first)
        self.assertIn("Opportunities", tables_first)

        # Second initialization (idempotent check)
        db_mgr.initialize_database()
        tables_second = db_mgr.get_existing_tables()
        self.assertEqual(set(tables_first), set(tables_second))
        db_mgr.close()


if __name__ == "__main__":
    unittest.main()
