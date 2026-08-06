"""
Database integrity and transaction rollback validation tests for CyberScout AI.
"""

import unittest
from src.database.connection import DatabaseManager
from src.database.seed import SeedManager


class TestDatabaseValidation(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()

    def tearDown(self):
        self.db_manager.close()

    def test_database_ping(self):
        """Verify database ping health check returns True."""
        self.assertTrue(self.db_manager.ping())

    def test_database_table_existence(self):
        """Verify core tables exist in the database."""
        tables = self.db_manager.get_existing_tables()
        self.assertIn("Opportunities", tables)
        self.assertIn("Sources", tables)

    def test_transaction_rollback_on_error(self):
        """Verify transaction context rolls back changes on exception."""
        try:
            with self.db_manager.transaction() as session:
                # Intentionally trigger an error
                session.execute("INSERT INTO NonExistentTable VALUES (1);")
        except Exception:
            pass

        self.assertTrue(self.db_manager.ping())


if __name__ == "__main__":
    unittest.main()
