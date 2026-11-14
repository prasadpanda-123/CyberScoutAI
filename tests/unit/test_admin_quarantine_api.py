import unittest
from contextlib import contextmanager
from unittest.mock import patch

from flask import Flask

import dashboard.routes.admin as admin_routes


class FakeCursor:
    def __init__(self):
        self.statements = []
        self.rowcount = 0
        self._result = None

    def execute(self, sql, parameters=()):
        self.statements.append((sql, parameters))
        if 'UPDATE "Opportunities"' in sql:
            self.rowcount = 1
        elif 'UPDATE "DiscoveredCandidates"' in sql:
            self.rowcount = 1
        elif "to_regclass" in sql:
            self._result = ("DiscoveredCandidates",)

    def fetchone(self):
        result = self._result
        self._result = None
        return result


class FakeDatabaseManager:
    def __init__(self):
        self.cursor = FakeCursor()

    @contextmanager
    def transaction(self):
        yield self.cursor


class TestAdminQuarantineApi(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="test-secret", TESTING=True)
        self.app.register_blueprint(admin_routes.admin_bp)
        self.client = self.app.test_client()

    def _authenticate_admin(self):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_username"] = "reviewer"
            sess["admin_role"] = "Administrator"


    def test_json_quarantine_action_updates_and_reports_success(self):
        self._authenticate_admin()
        db_manager = FakeDatabaseManager()
        with patch("src.database.connection.DatabaseManager", return_value=db_manager), \
             patch.object(admin_routes.audit_repo, "log_event"):
            response = self.client.post(
                "/admin/quarantine/action",
                json={
                    "action": "approve",
                    "item_id": "candidate-1",
                    "record_type": "Production Opportunity",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "action": "approve"})
        update_sql, parameters = db_manager.cursor.statements[0]
        self.assertIn("quality_status = 'quarantined'", update_sql)
        self.assertEqual(parameters, ("candidate-1",))
        self.assertEqual(len(db_manager.cursor.statements), 1)

    def test_staged_candidate_action_is_isolated_from_production_records(self):
        self._authenticate_admin()
        db_manager = FakeDatabaseManager()
        with patch("src.database.connection.DatabaseManager", return_value=db_manager), \
             patch.object(admin_routes.audit_repo, "log_event"):
            response = self.client.post(
                "/admin/quarantine/action",
                json={
                    "action": "reject",
                    "item_id": "candidate-2",
                    "record_type": "Staged Candidate",
                },
            )

        self.assertEqual(response.status_code, 200)
        statements = [sql for sql, _ in db_manager.cursor.statements]
        self.assertTrue(any('UPDATE "DiscoveredCandidates"' in sql for sql in statements))
        self.assertFalse(any('UPDATE "Opportunities"' in sql for sql in statements))


if __name__ == "__main__":
    unittest.main()
