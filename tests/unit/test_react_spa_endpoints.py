"""
Unit tests for React SPA shell route and missing JSON API endpoints.
Validates:
- GET /app and GET /app/<path:subpath>
- GET /api/me (unauthenticated and authenticated)
- GET /api/opportunities/<opportunity_id>
- GET /api/notifications
- GET /api/insights
- GET /api/quality/stats
- GET /admin/api/users
- POST /admin/api/users
- PATCH /admin/api/users/<user_id>
- DELETE /admin/api/users/<user_id>
- GET /admin/api/source-health
- GET /admin/api/data-quality
- GET /admin/api/diagnostics
"""

import uuid
import pytest
from flask import session
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class SPAEndpointsTestConfig(DashboardConfig):
    TESTING = True
    SECRET_KEY = "test_spa_endpoints_secret_key_12345"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    app = create_app(SPAEndpointsTestConfig)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_react_app_shell(client):
    """GET /app and /app/<path:subpath> serve the React SPA shell template with 200."""
    res = client.get("/app")
    assert res.status_code == 200
    assert b'<div id="root"></div>' in res.data
    assert b'meta name="csrf-token"' in res.data
    assert b'name="user-id"' not in res.data
    assert b'/static/react/assets/index.js' in res.data

    res_subpath = client.get("/app/opportunities/detail/test-id")
    assert res_subpath.status_code == 200
    assert b'<div id="root"></div>' in res_subpath.data


def test_api_me_unauthenticated(client):
    """GET /api/me returns 200 with authenticated=False and a CSRF token for unauthenticated visitors."""
    res = client.get("/api/me")
    assert res.status_code == 200
    data = res.get_json()
    assert data["authenticated"] is False
    assert data["user"] is None
    assert "csrf_token" in data
    assert len(data["csrf_token"]) > 0


def test_api_me_authenticated_user(client):
    """GET /api/me returns 200 with user profile when logged in as standard user."""
    user_id = str(uuid.uuid4())
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "alice"
        sess["email"] = "alice@cyberscout.ai"
        sess["role"] = "Operator"
        sess["user_csrf_token"] = "alice_token_123"

    res = client.get("/api/me")
    assert res.status_code == 200
    data = res.get_json()
    assert data["authenticated"] is True
    assert "id" not in data["user"]
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@cyberscout.ai"
    assert data["user"]["role"] == "Operator"
    assert "is_admin" not in data["user"]
    assert data["csrf_token"] == "alice_token_123"


def test_api_me_authenticated_admin(client):
    """GET /api/me returns 200 with admin profile when logged in as admin."""
    with client.session_transaction() as sess:
        sess["admin_authenticated"] = True
        sess["admin_user_id"] = 1
        sess["admin_username"] = "superadmin"
        sess["email"] = "admin@cyberscout.ai"
        sess["admin_role"] = "Administrator"
        sess["admin_csrf_token"] = "admin_token_999"

    res = client.get("/api/me")
    assert res.status_code == 200
    data = res.get_json()
    assert data["authenticated"] is True
    assert data["user"]["username"] == "superadmin"
    assert "id" not in data["user"]
    assert data["user"]["is_admin"] is True
    assert data["csrf_token"] == "admin_token_999"


def test_api_quality_stats(client):
    """GET /api/quality/stats returns quality stats for authenticated user."""
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid.uuid4())
        sess["role"] = "Viewer"

    res = client.get("/api/quality/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "stats" in data
    assert "accepted_count" in data["stats"]
    assert "rejected_count" in data["stats"]


def test_api_notifications(client):
    """GET /api/notifications returns user notifications list and unread count."""
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid.uuid4())
        sess["role"] = "Viewer"

    res = client.get("/api/notifications")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "notifications" in data
    assert "unread_count" in data
    assert isinstance(data["notifications"], list)


def test_api_insights(client):
    """GET /api/insights returns insights intelligence for authenticated user."""
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid.uuid4())
        sess["role"] = "Viewer"

    res = client.get("/api/insights")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "insights" in data


def test_api_opportunity_detail_not_found(client):
    """GET /api/opportunities/<id> returns 404 if opportunity does not exist."""
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid.uuid4())
        sess["role"] = "Viewer"

    res = client.get("/api/opportunities/non_existent_opp_id_999999")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"


def test_admin_api_users_forbidden_for_standard_user(client):
    """GET /admin/api/users returns 403 for non-admin user."""
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid.uuid4())
        sess["role"] = "Viewer"

    res = client.get("/admin/api/users")
    assert res.status_code == 403


def test_admin_api_endpoints_for_admin(client):
    """Admin API endpoints return successful JSON responses for authenticated admin."""
    with client.session_transaction() as sess:
        sess["admin_authenticated"] = True
        sess["admin_user_id"] = 1
        sess["admin_username"] = "admin"
        sess["admin_role"] = "Administrator"
        sess["admin_csrf_token"] = "test_admin_csrf"

    # GET /admin/api/users
    res = client.get("/admin/api/users")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "users" in data
    assert "admins" in data

    # GET /admin/api/source-health
    res = client.get("/admin/api/source-health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "sources" in data
    assert len(data["sources"]) >= 6

    # GET /admin/api/data-quality
    res = client.get("/admin/api/data-quality")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "metrics" in data
    assert "quarantine" in data

    # GET /admin/api/diagnostics
    res = client.get("/admin/api/diagnostics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "diagnostics" in data


def test_admin_api_user_crud(client):
    """Admin can create, toggle status, and delete user via Admin API."""
    unique_suffix = uuid.uuid4().hex[:8]
    test_username = f"api_test_user_{unique_suffix}"
    test_email = f"{test_username}@example.com"

    with client.session_transaction() as sess:
        sess["admin_authenticated"] = True
        sess["admin_user_id"] = 1
        sess["admin_username"] = "admin"
        sess["admin_role"] = "Administrator"
        sess["admin_csrf_token"] = "admin_csrf_crud_test"

    # 1. Create User
    res = client.post(
        "/admin/api/users",
        json={
            "username": test_username,
            "email": test_email,
            "password": "SecurePassword123!",
            "role": "Operator",
            "csrf_token": "admin_csrf_crud_test",
        },
    )
    assert res.status_code == 201, f"Create user failed: {res.data}"
    data = res.get_json()
    assert data["status"] == "success"

    # List users to find created user_id
    res_list = client.get("/admin/api/users")
    assert res_list.status_code == 200
    users = res_list.get_json()["users"]
    matched = [u for u in users if u["username"] == test_username]
    assert len(matched) == 1
    user_id = matched[0]["id"]
    initial_active = matched[0]["is_active"]

    # 2. Toggle Status
    res_toggle = client.patch(
        f"/admin/api/users/{user_id}",
        json={"csrf_token": "admin_csrf_crud_test"},
    )
    assert res_toggle.status_code == 200
    toggle_data = res_toggle.get_json()
    assert toggle_data["status"] == "success"
    assert toggle_data["is_active"] != initial_active

    # 3. Delete User
    res_delete = client.delete(
        f"/admin/api/users/{user_id}",
        json={"csrf_token": "admin_csrf_crud_test"},
    )
    assert res_delete.status_code == 200
    delete_data = res_delete.get_json()
    assert delete_data["status"] == "success"

    # Confirm deleted
    res_list_after = client.get("/admin/api/users")
    users_after = res_list_after.get_json()["users"]
    assert not any(u["id"] == user_id for u in users_after)

