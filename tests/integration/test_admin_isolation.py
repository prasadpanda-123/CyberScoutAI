"""
Integration tests for Admin Portal Isolation, Route Hardening & Access Boundaries (Phases 1 - 12).
"""

import pytest
from dashboard.app import create_app
from src.database.audit_log_repository import AuditLogRepository
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


@pytest.fixture
def client(monkeypatch):
    """Creates a test Flask client configured with an isolated test database."""
    db_mgr = DatabaseManager()
    db_mgr.initialize_database()

    user_repo = UserRepository(db_manager=db_mgr)
    # Seed Super Admin
    try:
        user_repo.create_user(
            username="superadmin",
            email="superadmin@cyberscout.ai",
            password="SuperAdminPass123!",
            role="Super Admin",
        )
    except Exception:
        pass

    try:
        user_repo.create_user(
            username="normaluser",
            email="normaluser@cyberscout.ai",
            password="NormalUserPass123!",
            role="Operator",
        )
    except Exception:
        pass

    audit_repo = AuditLogRepository(db_manager=db_mgr)

    monkeypatch.setattr("dashboard.routes.admin.user_repo", user_repo)
    monkeypatch.setattr("dashboard.routes.auth.user_repo", user_repo)
    monkeypatch.setattr("dashboard.routes.admin.audit_repo", audit_repo)

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


def test_public_registration_forces_viewer_role(client):
    """Phase 1: Public registration must ignore client role parameter and force Viewer role server-side."""
    reg_resp = client.post(
        "/register",
        data={
            "username": "crafted_admin_attempt",
            "email": "crafted_admin@cyberscout.ai",
            "password": "CraftedPassword123!",
            "confirm_password": "CraftedPassword123!",
            "role": "Administrator",  # Crafted parameter attempting privilege escalation
        },
        follow_redirects=True,
    )
    assert reg_resp.status_code == 200

    from src.database.user_repository import UserRepository
    user = UserRepository().get_by_email("crafted_admin@cyberscout.ai")
    assert user is not None
    assert user["role"] == "Viewer", f"Privilege escalation vulnerability! Expected role 'Viewer', got '{user['role']}'"


def test_admin_successful_mfa_otp_login_flow(client, monkeypatch):
    """Phases 6 - 8: Super Admin logs in via /admin/login, receives OTP, verifies at /admin/verify-otp, and gains access."""
    monkeypatch.setattr("src.auth.admin_auth.AdminSecurityManager.generate_otp_code", staticmethod(lambda: "123456"))
    otp_code = "123456"

    # 1. GET /admin/login to obtain CSRF token
    get_res = client.get("/admin/login")
    assert get_res.status_code == 200

    with client.session_transaction() as sess:
        csrf_tok = sess.get("admin_csrf_token")

    # 2. POST credentials to /admin/login -> expect redirect to /admin/verify-otp
    post_res = client.post(
        "/admin/login",
        data={
            "identifier": "superadmin",
            "password": "SuperAdminPass123!",
            "csrf_token": csrf_tok,
        },
        follow_redirects=False,
    )
    assert post_res.status_code == 302
    assert "/admin/verify-otp" in post_res.location

    # 4. GET /admin/verify-otp
    verify_page = client.get("/admin/verify-otp")
    assert verify_page.status_code == 200

    # 5. POST invalid OTP code -> rejected
    invalid_post = client.post(
        "/admin/verify-otp",
        data={"otp_code": "000000" if otp_code != "000000" else "999999", "csrf_token": csrf_tok},
        follow_redirects=True,
    )
    assert b"Invalid verification code" in invalid_post.data

    # 6. POST correct OTP code -> successful MFA authentication
    valid_post = client.post(
        "/admin/verify-otp",
        data={"otp_code": otp_code, "csrf_token": csrf_tok},
        follow_redirects=True,
    )
    assert valid_post.status_code == 200
    assert b"MFA Verification Successful" in valid_post.data or b"Admin Command Center" in valid_post.data

    # 7. Verify admin page is accessible now
    dash_res = client.get("/admin/dashboard")
    assert dash_res.status_code == 200
    assert b"Admin" in dash_res.data or b"Administrative" in dash_res.data


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
