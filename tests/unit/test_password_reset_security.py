import hashlib
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from flask import Blueprint, Flask
from werkzeug.security import check_password_hash

import dashboard.routes.auth as auth_routes
from src.database.password_reset_repository import PasswordResetRepository


class FakeCursor:
    def __init__(self):
        self.statements = []
        self.rowcount = 0
        self._result = None

    def execute(self, sql, parameters=()):
        self.statements.append((sql, parameters))
        if "RETURNING user_id" in sql:
            self._result = ("user-123",)
        if 'UPDATE "Users"' in sql:
            self.rowcount = 1

    def fetchone(self):
        result = self._result
        self._result = None
        return result

    def close(self):
        pass


class FakeDatabaseManager:
    def __init__(self):
        self.cursor = FakeCursor()
        self.commits = 0

    @contextmanager
    def transaction(self):
        yield self.cursor
        self.commits += 1


class TestPasswordResetSecurity(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            TESTING=True,
            APP_ENV="production",
            PUBLIC_APP_URL="https://cyberscout.example",
        )
        dashboard_bp = Blueprint("dashboard_ui", __name__)
        dashboard_bp.add_url_rule("/", "landing", lambda: "landing")
        self.app.register_blueprint(dashboard_bp)
        self.app.register_blueprint(auth_routes.auth_bp)
        self.client = self.app.test_client()

    def test_password_reset_email_uses_configured_origin_not_request_host(self):
        with self.app.test_request_context("/forgot-password", base_url="https://attacker.example"):
            with patch("src.notifier.providers.brevo_provider.BrevoEmailProvider.send_email") as send_email:
                send_email.return_value = {"status": "success"}
                self.assertTrue(
                    auth_routes._send_password_reset_email(
                        "user@example.com", "<script>alert(1)</script>", "opaque-token"
                    )
                )

        payload = send_email.call_args.kwargs
        self.assertIn("https://cyberscout.example/reset-password/opaque-token", payload["plain_content"])
        self.assertNotIn("attacker.example", payload["plain_content"])
        self.assertIn("&lt;script&gt;", payload["html_content"])
        self.assertNotIn("<script>", payload["html_content"])


    def test_reset_completion_consumes_hashed_token_and_revokes_sessions_atomically(self):
        db_manager = FakeDatabaseManager()
        repository = PasswordResetRepository(db_manager)
        raw_token = "single-use-secret"
        repository.store_token("user-123", raw_token)
        inserted = next(
            (sql, params)
            for sql, params in db_manager.cursor.statements
            if 'INSERT INTO "PasswordResetTokens"' in sql
        )
        self.assertEqual(inserted[1][0], hashlib.sha256(raw_token.encode()).hexdigest())
        self.assertNotIn(raw_token, inserted[1])

        new_password_hash = "pbkdf2:sha256$test"
        user_id = repository.complete_password_reset(raw_token, new_password_hash)
        self.assertEqual(user_id, "user-123")
        writes = [
            sql
            for sql, _ in db_manager.cursor.statements
            if "UPDATE " in sql
        ]
        self.assertIn('"PasswordResetTokens"', writes[0])
        self.assertIn('"Users"', writes[1])
        self.assertIn('"ServerSessions"', writes[2])
        self.assertIn("consumed_at IS NULL", writes[0])
        self.assertIn("expires_at > CURRENT_TIMESTAMP", writes[0])
        self.assertEqual(db_manager.commits, 3)

    def test_reset_post_updates_password_and_uses_atomic_repository_operation(self):
        password = "new-secure-password"
        with patch.object(auth_routes.password_reset_repo, "complete_password_reset", return_value="user-123") as complete, \
             patch.object(auth_routes.audit_repo, "log_event"):
            response = self.client.post(
                "/reset-password/single-use-token",
                data={
                    "new_password": password,
                    "confirm_password": password,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))
        raw_token, password_hash = complete.call_args.args
        self.assertEqual(raw_token, "single-use-token")
        self.assertTrue(check_password_hash(password_hash, password))


if __name__ == "__main__":
    unittest.main()
