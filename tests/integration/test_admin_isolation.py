"""
Integration tests for Admin Portal Isolation, Route Hardening & Access Boundaries (Phases 1 - 12).
"""

import pytest
from dashboard.app import create_app
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Creates a test Flask client configured with a isolated test database."""
    db_file = tmp_path / "test_admin_isolation.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.initialize_database()

    user_repo = UserRepository(db_manager=db_mgr)
    # Seed Super Admin
    user_repo.create_user(
        username="superadmin",
        email="superadmin@cyberscout.ai",
        password="SuperAdminPass123!",
        role="Super Admin",
    )
    # Seed Normal User
    user_repo.create_user(
        username="normaluser",
        email="normaluser@cyberscout.ai",
        password="NormalUserPass123!",
        role="Operator",
    )

    def mock_db_init(self, db_path=None):
        self.db_path = db_file
        self._connection = db_mgr.get_connection()

    monkeypatch.setattr(DatabaseManager, "__init__", mock_db_init)
    monkeypatch.setattr("dashboard.routes.admin.user_repo", user_repo)
    monkeypatch.setattr("dashboard.routes.auth.user_repo", user_repo)

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        yield client


def test_anonymous_access_to_admin_pages_redirects(client):
    """Phase 6: Anonymous visitors to leaked admin URLs must receive a 302 Redirect to /admin/login."""
    admin_urls = [
        "/admin/dashboard",
        "/admin/collectors",
        "/admin/scheduler",
        "/admin/logs",
        "/admin/configuration",
        "/admin/users",
        "/admin/reports",
        "/admin/diagnostics",
        "/admin/system",
    ]
    for url in admin_urls:
        response = client.get(url, follow_redirects=False)
        assert response.status_code == 302, f"Failed for URL: {url}"
        assert "/admin/login" in response.location


def test_anonymous_access_to_admin_apis_returns_401(client):
    """Phase 4: Anonymous API requests to admin endpoints must return HTTP 401 JSON."""
    api_urls = [
        "/admin/api/system",
        "/admin/api/logs",
        "/admin/api/config",
        "/admin/api/collectors",
        "/api/system",
        "/api/logs",
        "/api/config",
        "/api/collectors",
    ]
    for url in api_urls:
        response = client.get(url, headers={"Accept": "application/json"})
        assert response.status_code == 401, f"Failed for URL: {url}"
        data = response.get_json()
        assert data["status"] == "failed"
        assert "Authentication required" in data["error"] or "Admin authentication required" in data["error"]


def test_normal_user_access_to_admin_pages_returns_403(client):
    """Phase 2 & 6: Logged-in non-admin user accessing admin pages must receive HTTP 403 Forbidden."""
    # Log in as normal user via public /login
    login_resp = client.post(
        "/login",
        data={"identifier": "normaluser", "password": "NormalUserPass123!"},
        follow_redirects=True,
    )
    assert login_resp.status_code == 200

    admin_urls = [
        "/admin/dashboard",
        "/admin/collectors",
        "/admin/scheduler",
        "/admin/logs",
        "/admin/configuration",
        "/admin/users",
    ]
    for url in admin_urls:
        response = client.get(url)
        assert response.status_code == 403, f"Expected 403 for normal user on {url}, got {response.status_code}"
        assert b"403 Forbidden" in response.data or b"Forbidden" in response.data


def test_normal_user_access_to_admin_apis_returns_403(client):
    """Phase 4: Logged-in non-admin user requesting admin APIs must receive HTTP 403 JSON."""
    client.post(
        "/login",
        data={"identifier": "normaluser", "password": "NormalUserPass123!"},
        follow_redirects=True,
    )

    api_urls = [
        "/admin/api/system",
        "/admin/api/logs",
        "/admin/api/config",
        "/api/system",
        "/api/logs",
        "/api/config",
    ]
    for url in api_urls:
        response = client.get(url, headers={"Accept": "application/json"})
        assert response.status_code == 403, f"Expected 403 for normal user API call to {url}"
        data = response.get_json()
        assert data["status"] == "failed"
        assert "Forbidden" in data["error"] or "Access denied" in data["error"]


def test_normal_user_cannot_authenticate_at_admin_login(client):
    """Phase 1: Normal user credentials must be rejected at /admin/login."""
    response = client.post(
        "/admin/login",
        data={"identifier": "normaluser", "password": "NormalUserPass123!", "csrf_token": "dummy"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Access Denied: Standard user accounts cannot authenticate" in response.data or b"CSRF validation failed" in response.data


def test_admin_successful_login_flow(client):
    """Phase 1 & 7: Super Admin authenticates at /admin/login, establishes session, and accesses dashboard."""
    # First GET /admin/login to establish csrf token
    get_res = client.get("/admin/login")
    assert get_res.status_code == 200

    with client.session_transaction() as sess:
        csrf_tok = sess.get("admin_csrf_token")

    post_res = client.post(
        "/admin/login",
        data={
            "identifier": "superadmin",
            "password": "SuperAdminPass123!",
            "csrf_token": csrf_tok,
        },
        follow_redirects=True,
    )
    assert post_res.status_code == 200
    assert b"Administrator Portal Session Established" in post_res.data or b"Admin Command Center" in post_res.data

    # Verify protected admin page accessible now
    dash_res = client.get("/admin/dashboard")
    assert dash_res.status_code == 200
    assert b"Admin Command Center" in dash_res.data

    # Verify admin API accessible
    api_res = client.get("/admin/api/system")
    assert api_res.status_code == 200
    assert api_res.get_json()["app_name"] == "CyberScout AI"


def test_admin_logout_flow(client):
    """Phase 1: Admin logout terminates admin session namespace."""
    client.get("/admin/login")
    with client.session_transaction() as sess:
        csrf_tok = sess.get("admin_csrf_token")

    client.post(
        "/admin/login",
        data={"identifier": "superadmin", "password": "SuperAdminPass123!", "csrf_token": csrf_tok},
    )

    # Logout
    logout_res = client.get("/admin/logout", follow_redirects=True)
    assert logout_res.status_code == 200

    # Verify admin page redirects now
    dash_res = client.get("/admin/dashboard", follow_redirects=False)
    assert dash_res.status_code == 302
    assert "/admin/login" in dash_res.location


def test_robots_txt_disallows_admin(client):
    """Phase 9: robots.txt disallows crawler indexing of /admin/*."""
    res = client.get("/robots.txt")
    assert res.status_code == 200
    assert b"Disallow: /admin/" in res.data
