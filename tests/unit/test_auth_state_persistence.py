from contextlib import contextmanager
import time

from flask import Flask, Response, session
import pytest

from dashboard.sessions import PostgresSessionInterface, ServerSideSession
from dashboard.routes import admin as admin_routes
from src.auth.admin_auth import AdminSecurityManager
from src.database.mfa_repository import MfaRepository
from src.database.session_repository import generate_session_id


class UnavailableTransaction:
    def __enter__(self):
        raise RuntimeError("database unavailable")

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class UnavailableDatabaseManager:
    def transaction(self):
        return UnavailableTransaction()


class RecordingCursor:
    def __init__(self, fail_on_cleanup=False):
        self.fail_on_cleanup = fail_on_cleanup
        self.executed = []

    def execute(self, sql, parameters=()):
        self.executed.append((sql, parameters))
        if self.fail_on_cleanup and sql.lstrip().startswith("DELETE"):
            raise RuntimeError("cleanup failed")


class RecordingDatabaseManager:
    def __init__(self, cursor):
        self.cursor = cursor

    @contextmanager
    def transaction(self):
        yield self.cursor


def test_mfa_repository_surfaces_database_read_failures():
    repository = MfaRepository.__new__(MfaRepository)
    repository.db_manager = UnavailableDatabaseManager()

    with pytest.raises(RuntimeError, match="database unavailable"):
        repository.get_pending_mfa("test-pending-token")


def test_admin_mfa_read_uses_cache_only_when_database_read_fails(monkeypatch):
    repository = MfaRepository.__new__(MfaRepository)
    repository.db_manager = UnavailableDatabaseManager()
    token = "test-pending-token"
    state = {
        "user_id": 1,
        "username": "test-admin",
        "otp_hash": "test-hash",
        "expires_at": int(time.time()) + 300,
        "attempts": 0,
    }
    monkeypatch.setattr(AdminSecurityManager, "_mfa_repo", repository)
    monkeypatch.setattr(AdminSecurityManager, "_pending_mfa_sessions", {token: state})

    assert AdminSecurityManager.get_pending_mfa(token) == state
    assert AdminSecurityManager._pending_mfa_sessions[token] == state


def test_admin_mfa_read_does_not_use_cache_when_database_reports_missing_token(monkeypatch):
    class MissingMfaRepository:
        def get_pending_mfa(self, _token):
            return None

    token = "test-pending-token"
    monkeypatch.setattr(AdminSecurityManager, "_mfa_repo", MissingMfaRepository())
    monkeypatch.setattr(
        AdminSecurityManager,
        "_pending_mfa_sessions",
        {token: {"expires_at": int(time.time()) + 300}},
    )

    assert AdminSecurityManager.get_pending_mfa(token) is None
    assert token not in AdminSecurityManager._pending_mfa_sessions


def test_admin_mfa_store_fails_if_database_persistence_fails(monkeypatch):
    class FailingMfaRepository:
        def store_pending_mfa(self, **_kwargs):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(AdminSecurityManager, "_mfa_repo", FailingMfaRepository())
    cache = {}
    monkeypatch.setattr(AdminSecurityManager, "_pending_mfa_sessions", cache)

    with pytest.raises(RuntimeError, match="Unable to persist"):
        AdminSecurityManager.store_pending_mfa(
            user_id=1,
            username="test-admin",
            email="test@example.com",
            role="Admin",
            otp_hash="test-hash",
            expires_at=int(time.time()) + 300,
        )

    assert cache == {}


def test_admin_mfa_repository_uses_string_account_ids_for_cleanup_and_insert():
    cursor = RecordingCursor()
    repository = MfaRepository.__new__(MfaRepository)
    repository.db_manager = RecordingDatabaseManager(cursor)

    repository.store_pending_mfa(
        token="test-pending-token",
        user_id=123,
        username="test-admin",
        email="test@example.com",
        role="Admin",
        otp_hash="test-hash",
        expires_at=int(time.time()) + 300,
    )

    assert cursor.executed[0][1] == ("123", "admin_login_mfa")
    assert cursor.executed[1][1][2] == "123"


def test_admin_mfa_cleanup_failure_prevents_partial_insert():
    cursor = RecordingCursor(fail_on_cleanup=True)
    repository = MfaRepository.__new__(MfaRepository)
    repository.db_manager = RecordingDatabaseManager(cursor)

    with pytest.raises(RuntimeError, match="cleanup failed"):
        repository.store_pending_mfa(
            token="test-pending-token",
            user_id=123,
            username="test-admin",
            email="test@example.com",
            role="Admin",
            otp_hash="test-hash",
            expires_at=int(time.time()) + 300,
        )

    assert len(cursor.executed) == 1


def test_password_change_repository_uses_string_account_ids():
    cursor = RecordingCursor()
    repository = MfaRepository.__new__(MfaRepository)
    repository.db_manager = RecordingDatabaseManager(cursor)

    repository.store_pending_password_change(
        token="test-password-token",
        target_type="admin",
        account_id=606,
        username="test-admin",
        email="test@example.com",
        new_password_hash="test-password-hash",
        otp_hash="test-otp-hash",
        expires_at=int(time.time()) + 300,
    )

    assert cursor.executed[0][1] == ("606", "admin_pw_change")
    assert cursor.executed[1][1][2] == "606"


def test_admin_login_returns_service_unavailable_if_mfa_cannot_be_persisted(monkeypatch):
    class AdminRepository:
        def authenticate(self, _identifier, _password):
            return {
                "id": 1,
                "username": "test-admin",
                "email": "test@example.com",
                "role": "Admin",
            }

    monkeypatch.setattr(admin_routes, "admin_repo", AdminRepository())
    monkeypatch.setattr(AdminSecurityManager, "consume_login_attempt", lambda *_args: True)

    def fail_to_store_mfa(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        AdminSecurityManager,
        "store_pending_mfa",
        staticmethod(fail_to_store_mfa),
    )

    app = Flask(__name__)
    app.secret_key = "test-secret-key-for-unit-test"
    with app.test_request_context(
        "/admin/login",
        method="POST",
        json={
            "username": "test-admin",
            "password": "valid-password",
            "next": "/admin/dashboard",
        },
    ):
        response, status = admin_routes.admin_login()

    assert status == 503
    assert response.get_json()["status"] == "failed"


def test_admin_otp_returns_service_unavailable_if_state_cannot_be_loaded(monkeypatch):
    def fail_to_load_mfa(_token):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        AdminSecurityManager,
        "get_pending_mfa",
        staticmethod(fail_to_load_mfa),
    )
    app = Flask(__name__)
    app.secret_key = "test-secret-key-for-unit-test"
    with app.test_request_context(
        "/admin/verify-otp",
        method="POST",
        json={"otp": "123456"},
    ):
        session["admin_pending_token"] = "test-pending-token"
        response, status = admin_routes.admin_verify_otp()

    assert status == 503
    assert response.get_json()["status"] == "failed"


def test_session_interface_does_not_issue_cookie_when_persistence_fails():
    class FailingSessionRepository:
        def save_session(self, **_kwargs):
            return False

    interface = PostgresSessionInterface(FailingSessionRepository())
    session = ServerSideSession(sid=generate_session_id())
    session["admin_pending_token"] = "test-token"
    app = Flask(__name__)
    app.config["SESSION_COOKIE_NAME"] = "cyberscout_session"

    with app.test_request_context("/admin/login"):
        response = Response()
        with pytest.raises(RuntimeError, match="persist"):
            interface.save_session(app, session, response)
        assert "Set-Cookie" not in response.headers
