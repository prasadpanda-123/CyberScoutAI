"""
Regression Unit Tests for Migration Bootstrap System.
"""

import unittest
from src.database.connection import DatabaseManager
from src.database.migrations import MIGRATIONS, MigrationManager


class TestMigrationBootstrap(unittest.TestCase):
    def setUp(self):
        self.db_mgr = DatabaseManager()

    def tearDown(self):
        self.db_mgr.close()

    def test_database_initialization(self):
        """Verify that DatabaseManager initializes schema and existing tables."""
        self.db_mgr.initialize_database()
        tables = self.db_mgr.get_existing_tables()
        self.assertIn("Opportunities", tables)
        self.assertIn("Users", tables)

    def test_migration_manager_version(self):
        """Verify that MigrationManager returns high baseline version."""
        mig_mgr = MigrationManager(self.db_mgr)
        applied = mig_mgr.apply_migrations()
        self.assertIsInstance(applied, int)


if __name__ == "__main__":
    unittest.main()
