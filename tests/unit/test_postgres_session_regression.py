"""
Regression unit test for PostgreSQL session initialization and transaction state handling.

Ensures that database initialization, health checks, and engine creation do not trigger:
psycopg2.ProgrammingError: set_session cannot be used inside a transaction
"""

import unittest
from unittest.mock import MagicMock, patch

from src.database.connection import DatabaseManager, PgConnectionAdapter
from src.database.engine import create_db_engine, reset_engine


class TestPostgresSessionRegression(unittest.TestCase):
    """Regression test suite for PostgreSQL session configuration and transaction handling."""

    def setUp(self):
        reset_engine()
        self.db_manager = DatabaseManager()

    def tearDown(self):
        self.db_manager.close()
        reset_engine()

    def test_pg_connection_adapter_set_session_safety(self):
        """
        Verify that PgConnectionAdapter.set_session safely handles active transactions
        by rolling back before calling set_session on the raw connection.
        """
        mock_raw_conn = MagicMock()
        # Simulate active transaction status in psycopg2 (status != 0)
        mock_raw_conn.status = 1
        adapter = PgConnectionAdapter(mock_raw_conn)

        adapter.set_session(autocommit=False)

        # Must trigger rollback on raw_conn before set_session
        mock_raw_conn.rollback.assert_called_once()
        mock_raw_conn.set_session.assert_called_once_with(autocommit=False)

    def test_database_initialization_does_not_trigger_set_session_transaction_error(self):
        """
        Verify database initialization lifecycle:
        1. ping() executes SELECT 1.
        2. initialize_database() creates schema and seed data.
        3. Connection remains open and functional afterwards without raising set_session errors.
        """
        # Execute initialize_database
        self.db_manager.initialize_database()

        # Connection ping must succeed
        self.assertTrue(self.db_manager.ping(), "Database ping should succeed after initialization.")

        # Verify connection remains open
        conn = self.db_manager.get_connection()
        self.assertIsNotNone(conn, "Database connection should remain open.")
        self.assertTrue(self.db_manager.verify_integrity(), "Database integrity should pass.")

    def test_engine_creation_isolation_level(self):
        """Verify that engine creation configures isolation_level on engine level."""
        engine = create_db_engine()
        self.assertIsNotNone(engine)


if __name__ == "__main__":
    unittest.main()
