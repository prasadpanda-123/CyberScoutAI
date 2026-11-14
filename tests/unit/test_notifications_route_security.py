import pytest
from flask import Flask, request, session
from unittest.mock import MagicMock, patch

from dashboard.routes.notifications import notifications_bp
from src.models.recommendation_models import UserPreferencesDTO








def _client_with_user():
    app = Flask(__name__)
    app.secret_key = "unit-test-secret"
    app.register_blueprint(notifications_bp)
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = "a22d7d79-52f7-49b0-9003-1769f7d93155"
    return client


def test_preferences_get_returns_authenticated_user_settings():
    repo = MagicMock()
    repo.get_preferences.return_value = UserPreferencesDTO(email_notifications_enabled=False)
    with patch("dashboard.routes.notifications.DatabaseManager"), patch(
        "dashboard.routes.notifications.UserPreferencesRepository", return_value=repo
    ):
        response = _client_with_user().get(
            "/notifications/preferences",
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    assert response.get_json()["preferences"]["email_notifications_enabled"] is False


def test_preferences_json_update_preserves_unsubmitted_preferences():
    existing = UserPreferencesDTO(skills=["python"], email_notifications_enabled=True)
    repo = MagicMock()
    repo.get_preferences.return_value = existing
    repo.save_preferences.return_value = True
    audit_repo = MagicMock()
    with patch("dashboard.routes.notifications.DatabaseManager"), patch(
        "dashboard.routes.notifications.UserPreferencesRepository", return_value=repo
    ), patch("dashboard.routes.notifications.AuditLogRepository", return_value=audit_repo):
        response = _client_with_user().post(
            "/notifications/preferences",
            json={"email_notifications_enabled": False, "delivery_mode": "digest", "digest_frequency": "weekly"},
        )

    saved_preferences = repo.save_preferences.call_args.kwargs["preferences"]
    assert response.status_code == 200
    assert saved_preferences.email_notifications_enabled is False
    assert saved_preferences.skills == ["python"]
    assert saved_preferences.delivery_mode == "digest"
    assert saved_preferences.digest_frequency == "weekly"
