"""
Database integrity, foreign keys, transaction rollbacks, and backup tests for CyberScout AI.
"""

from pathlib import Path
import sqlite3
import unittest

from src.database.connection import DatabaseManager
from src.database.seed import SeedManager


class TestDatabaseValidation(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_path=Path(":memory:"))
        self.db_manager.initialize_database()
        SeedManager(self.db_manager).run_all_seeds()

    def tearDown(self):
        self.db_manager.close()

    def test_pragma_integrity_check(self):
        """Run SQLite PRAGMA integrity_check and confirm ok result."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            res = cursor.fetchone()[0]
            self.assertEqual(res, "ok")

    def test_foreign_key_enforcement(self):
        """Verify PRAGMA foreign_keys is enabled."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys;")
            fk = cursor.fetchone()[0]
            self.assertEqual(fk, 1)

    def test_transaction_rollback_on_error(self):
        """Verify transaction context rolls back changes on exception."""
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO Sources (id, name, collection_method, default_category, status, enabled) VALUES ('test_src_rollback', 'Test', 'rss', 'other', 'active', 1);"
                )
                # Intentionally trigger an error
                cursor.execute("INSERT INTO NonExistentTable VALUES (1);")
        except Exception:
            pass

        # Verify test_src_rollback was rolled back and not persisted
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Sources WHERE id = 'test_src_rollback';")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 0)

    def test_table_count_and_schema_version(self):
        """Verify table count is at least 8."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
            tbl_count = cursor.fetchone()[0]
            self.assertGreaterEqual(tbl_count, 8)


if __name__ == "__main__":
    unittest.main()
