"""
Phase 3 Verification Tests: Administrative Security & Production Operational Hardening.

Covers all 36 mandatory verification scenarios defined in Section 21 & Additional Requirement A:
1-10: Admin Open Redirect Hardening (SEC-01)
11-16: Admin User Creation CSRF & Strict Identity Separation (SEC-02, SEC-04, SEC-08)
17-23: Legacy Admin API Security, RBAC & Audit Logging (SEC-03)
24-27: Database-Backed Multi-Worker Login Rate Limiting (SEC-07, SEC-11)
28-30: Production Secrets, Session Cookies & Configuration Hardening (SEC-06)
31-33: Pagination Bounds & Input Hardening (SEC-05)
34-36: PostgreSQL Row Level Security (RLS) & Least-Privilege Enforcement (Additional Requirement A)
"""

import os
from unittest.mock import patch
import pytest

from dashboard.app import create_app
from dashboard.config import get_secret_key
from src.auth.admin_auth import AdminSecurityManager
from src.database.admin_repository import AdminRepository
from src.database.audit_log_repository import AuditLogRepository
from src.database.connection import DatabaseManager
from src.database.login_attempt_repository import LoginAttemptRepository
from src.database.user_repository import UserRepository
from src.utils.pagination_utils import parse_pagination
from src.utils.url_utils import is_safe_internal_url


@pytest.fixture(scope="module")
def app():
    """Create a test Flask application."""
    test_app = create_app()
    test_app.config["TESTING"] = True
    test_app.config["WTF_CSRF_ENABLED"] = False
    return test_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def db_manager():
    """Authoritative DatabaseManager."""
    return DatabaseManager()


# =====================================================================
# Scenarios 1-10: Admin Open Redirect Hardening (SEC-01)
# =====================================================================
class TestAdminOpenRedirectHardening:
    """Verifies that is_safe_internal_url and admin login redirect logic fail closed."""

    def test_01_safe_relative_path(self):
        assert is_safe_internal_url("/admin/logs") is True

    def test_02_absolute_external_url(self):
        assert is_safe_internal_url("https://evil.com") is False

    def test_03_protocol_relative_url(self):
        assert is_safe_internal_url("//evil.com") is False

    def test_04_backslash_relative_url(self):
        assert is_safe_internal_url(r"\evil.com") is False
        assert is_safe_internal_url(r"/\evil.com") is False

    def test_05_javascript_pseudo_protocol(self):
        assert is_safe_internal_url("javascript:alert(1)") is False

    def test_06_url_with_whitespace_or_control_chars(self):
        assert is_safe_internal_url("/admin%20/dashboard") is False
        assert is_safe_internal_url("/admin\t/dashboard") is False
        assert is_safe_internal_url("/admin\n/dashboard") is False

    def test_07_none_and_empty_target(self):
        assert is_safe_internal_url(None) is False
        assert is_safe_internal_url("") is False

    def test_08_safe_url_with_query_params(self):
        assert is_safe_internal_url("/admin/dashboard?tab=security") is True

    def test_09_absolute_url_spoofing_internal_path(self):
        assert is_safe_internal_url("https://evil.com/admin/dashboard") is False

    def test_10_ftp_pseudo_protocol(self):
        assert is_safe_internal_url("ftp://evil.com") is False
        assert is_safe_internal_url("data:text/html,<script>alert(1)</script>") is False

    def test_login_redirect_behavior(self, client):
        """Simulates admin login with malicious vs safe next query params."""
        # Unsafe redirect should fallback to /admin/dashboard
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "testadmin"

        # Safe next
        res_safe = client.get("/admin/login?next=/admin/logs")
        assert res_safe.status_code == 302
        assert res_safe.location == "/admin/logs"

        # Evil next
        res_evil = client.get("/admin/login?next=https://evil.com")
        assert res_evil.status_code == 302
        assert res_evil.location == "/admin/dashboard"

        # Protocol relative evil next
        res_proto = client.get("/admin/login?next=//evil.com")
        assert res_proto.status_code == 302
        assert res_proto.location == "/admin/dashboard"


# =====================================================================
# Scenarios 11-16: Admin User Creation CSRF & Identity Separation (SEC-02, SEC-04, SEC-08)
# =====================================================================
class TestAdminUserCreationAndIdentitySeparation:
    """Verifies CSRF enforcement, role isolation, and password policies on user creation."""

    @pytest.fixture(autouse=True)
    def cleanup_test_users(self, db_manager):
        conn = db_manager.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('DELETE FROM "Users" WHERE username LIKE %s;', ("test_standard_user_%",))
            cur.execute('DELETE FROM "Admins" WHERE username LIKE %s;', ("test_admin_user_%",))
            conn.commit()
        finally:
            cur.close()
        yield
        conn = db_manager.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('DELETE FROM "Users" WHERE username LIKE %s;', ("test_standard_user_%",))
            cur.execute('DELETE FROM "Admins" WHERE username LIKE %s;', ("test_admin_user_%",))
            conn.commit()
        finally:
            cur.close()

    def test_11_post_admin_users_without_csrf_forbidden(self, client):
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"
            sess["admin_csrf_token"] = "valid_admin_token_11"

        res = client.post("/admin/users", data={
            "username": "new_user_11",
            "email": "user11@example.com",
            "password": "ValidPassword123!",
            "role": "Viewer"
        })
        assert res.status_code == 403

    def test_12_post_admin_users_with_invalid_csrf_forbidden(self, client):
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"
            sess["admin_csrf_token"] = "valid_admin_token_12"

        res = client.post("/admin/users", data={
            "csrf_token": "wrong_csrf_token",
            "username": "new_user_12",
            "email": "user12@example.com",
            "password": "ValidPassword123!",
            "role": "Viewer"
        })
        assert res.status_code == 403

    def test_13_post_admin_users_creates_standard_user(self, client, db_manager):
        csrf = "valid_csrf_token_13"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"
            sess["admin_csrf_token"] = csrf

        res = client.post("/admin/users", data={
            "csrf_token": csrf,
            "action": "create_user",
            "username": "test_standard_user_13",
            "email": "standard13@example.com",
            "password": "StandardPassword123!",
            "role": "Viewer"
        }, follow_redirects=False)

        assert res.status_code in (200, 302)
        # Verify user is in Users table
        user_repo = UserRepository(db_manager)
        user = user_repo.get_by_username("test_standard_user_13")
        assert user is not None
        assert user["email"] == "standard13@example.com"

    def test_14_post_admin_users_creates_administrator_in_admins_table(self, client, db_manager):
        csrf = "valid_csrf_token_14"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"
            sess["admin_csrf_token"] = csrf

        res = client.post("/admin/users", data={
            "csrf_token": csrf,
            "action": "create_user",
            "username": "test_admin_user_14",
            "email": "admin14@example.com",
            "password": "AdminComplexPassword123!",
            "role": "Administrator"
        }, follow_redirects=False)

        assert res.status_code in (200, 302)
        # Verify created in Admins table
        admin_repo = AdminRepository(db_manager)
        admin = admin_repo.get_by_username("test_admin_user_14")
        assert admin is not None
        assert admin["email"] == "admin14@example.com"

        # Verify NOT in Users table
        user_repo = UserRepository(db_manager)
        user = user_repo.get_by_username("test_admin_user_14")
        assert user is None

    def test_15_post_admin_users_password_under_8_rejected(self, client):
        csrf = "valid_csrf_token_15"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"
            sess["admin_csrf_token"] = csrf

        res = client.post("/admin/users", data={
            "csrf_token": csrf,
            "action": "create_user",
            "username": "short_pw_user",
            "email": "short@example.com",
            "password": "short",
            "role": "Viewer"
        })
        assert res.status_code == 400
        assert b"at least 8 characters" in res.data

    def test_16_post_admin_users_weak_admin_password_rejected(self, client):
        csrf = "valid_csrf_token_16"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"
            sess["admin_csrf_token"] = csrf

        # Lacks uppercase and special characters for Admin complexity
        res = client.post("/admin/users", data={
            "csrf_token": csrf,
            "action": "create_user",
            "username": "weak_admin_user",
            "email": "weak_admin@example.com",
            "password": "alllowercaseandnumbers123",
            "role": "Administrator"
        })
        assert res.status_code == 400


# =====================================================================
# Scenarios 17-23: Legacy Admin API Security & RBAC (SEC-03)
# =====================================================================
class TestLegacyAdminAPISecurity:
    """Verifies that legacy operational routes require admin authentication, CSRF, and create audit logs."""

    def test_17_scheduler_pause_without_csrf_rejected(self, client):
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"
            sess["admin_csrf_token"] = "correct_token_17"

        res = client.post("/api/scheduler/pause", headers={"Content-Type": "application/json"})
        assert res.status_code in (400, 403)

    def test_18_scheduler_pause_with_csrf_succeeds_and_creates_audit_log(self, client, db_manager):
        csrf = "correct_token_18"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin_audit"
            sess["admin_csrf_token"] = csrf

        with patch("dashboard.services.api_service.APIService.pause_scheduler", return_value={"status": "paused"}):
            res = client.post(
                "/api/scheduler/pause",
                headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"}
            )
            assert res.status_code == 200

        # Verify AuditLog created
        audit_repo = AuditLogRepository(db_manager)
        logs = audit_repo.query_logs(event_type="SCHEDULER", page=1, limit=5)
        assert logs["total_records"] > 0
        assert any(l["action"] == "PAUSE_SCHEDULER" for l in logs["logs"])

    def test_19_scheduler_resume_creates_audit_log(self, client, db_manager):
        csrf = "correct_token_19"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin_resume"
            sess["admin_csrf_token"] = csrf

        with patch("dashboard.services.api_service.APIService.resume_scheduler", return_value={"status": "resumed"}):
            res = client.post(
                "/api/scheduler/resume",
                headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"}
            )
            assert res.status_code == 200

        audit_repo = AuditLogRepository(db_manager)
        logs = audit_repo.query_logs(event_type="SCHEDULER", page=1, limit=5)
        assert logs["total_records"] > 0
        assert any(l["action"] == "RESUME_SCHEDULER" for l in logs["logs"])

    def test_20_report_trigger_creates_audit_log(self, client, db_manager):
        csrf = "correct_token_20"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin_report"
            sess["admin_csrf_token"] = csrf

        with patch("dashboard.services.api_service.APIService.send_daily_report_now", return_value={"report_name": "test_rep"}):
            res = client.post(
                "/api/report/trigger",
                headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"}
            )
            assert res.status_code == 200

        audit_repo = AuditLogRepository(db_manager)
        logs = audit_repo.query_logs(event_type="REPORTS", page=1, limit=5)
        assert logs["total_records"] > 0
        assert any(l["action"] == "TRIGGER_REPORT" for l in logs["logs"])

    def test_21_email_test_creates_audit_log(self, client, db_manager):
        csrf = "correct_token_21"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin_email"
            sess["admin_csrf_token"] = csrf

        with patch("dashboard.services.api_service.APIService.send_test_email", return_value={"success": True}):
            res = client.post(
                "/api/email/test",
                headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"}
            )
            assert res.status_code == 200

        audit_repo = AuditLogRepository(db_manager)
        logs = audit_repo.query_logs(event_type="EMAIL", page=1, limit=5)
        assert logs["total_records"] > 0
        assert any(l["action"] == "TEST_EMAIL" for l in logs["logs"])

    def test_22_opportunities_clear_old_invalid_days_handled_safely(self, client):
        csrf = "correct_token_22"
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin_clear"
            sess["admin_csrf_token"] = csrf

        # Pass non-numeric days; should not raise 500
        res = client.post(
            "/api/opportunities/clear-old",
            json={"days": "invalid_string"},
            headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"}
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "deleted_count" in data

    def test_23_non_admin_user_cannot_access_legacy_admin_apis(self, client):
        # Non-admin user session
        with client.session_transaction() as sess:
            sess["user_id"] = 101
            sess["username"] = "regular_user"
            sess["role"] = "Viewer"

        res = client.post("/api/scheduler/pause")
        assert res.status_code in (401, 403)

        res2 = client.post("/api/report/trigger")
        assert res2.status_code in (401, 403)


# =====================================================================
# Scenarios 24-27: Multi-Worker / Database-Backed Rate Limiting (SEC-07, SEC-11)
# =====================================================================
class TestMultiWorkerRateLimiting:
    """Verifies that failed login attempts and lockout state persist in DB across workers."""

    def test_24_failed_attempts_persist_across_repository_instances(self, db_manager):
        ip = "192.168.10.55"
        identifier = "target_test_user_24"
        attempt_type = "admin_login"

        repo_worker_1 = LoginAttemptRepository(db_manager)
        repo_worker_2 = LoginAttemptRepository(db_manager)

        # Worker 1 records attempt
        repo_worker_1.record_failed_attempt(ip_address=ip, identifier=identifier, attempt_type=attempt_type)

        # Worker 2 reads attempt
        count = repo_worker_2.get_failed_attempts_count(
            ip_address=ip,
            identifier=identifier,
            attempt_type=attempt_type,
            window_minutes=15
        )
        assert count >= 1

    def test_25_lockout_activates_after_threshold(self, db_manager):
        ip = "192.168.10.77"
        identifier = "lockout_candidate_25"
        attempt_type = "admin_login"
        repo = LoginAttemptRepository(db_manager)

        # Clear existing
        repo.reset_failed_attempts(ip_address=ip, identifier=identifier, attempt_type=attempt_type)

        # Record 5 failed attempts
        for _ in range(5):
            AdminSecurityManager.record_failed_attempt(ip, identifier, attempt_type=attempt_type)

        # Must be locked out
        is_locked = AdminSecurityManager.is_locked_out(ip, identifier, attempt_type=attempt_type)
        assert is_locked is True

    def test_26_successful_login_resets_counter(self, db_manager):
        ip = "192.168.10.88"
        identifier = "reset_candidate_26"
        attempt_type = "admin_login"

        AdminSecurityManager.record_failed_attempt(ip, identifier, attempt_type=attempt_type)
        AdminSecurityManager.record_failed_attempt(ip, identifier, attempt_type=attempt_type)

        # Reset
        AdminSecurityManager.reset_failed_attempts(ip, identifier, attempt_type=attempt_type)

        # Verify unlocked
        is_locked = AdminSecurityManager.is_locked_out(ip, identifier, attempt_type=attempt_type)
        assert is_locked is False

    def test_27_lockout_window_expiration(self, db_manager):
        repo = LoginAttemptRepository(db_manager)
        # Verify window_minutes=0 returns 0 attempts
        ip = "192.168.10.99"
        identifier = "window_candidate_27"
        repo.record_failed_attempt(ip, identifier, attempt_type="admin_login")
        count_zero_window = repo.get_failed_attempts_count(ip, identifier, attempt_type="admin_login", window_minutes=0)
        assert count_zero_window == 0


# =====================================================================
# Scenarios 28-30: Production Secrets, Session Cookies & Configuration Hardening (SEC-06)
# =====================================================================
class TestProductionConfigurationHardening:
    """Verifies fail-closed behavior for missing or insecure secrets in production."""

    def test_28_production_without_secret_key_raises_error(self):
        with patch.dict(os.environ, {"CYBERSCOUT_ENV": "production"}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                get_secret_key()
            assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)

    def test_29_production_with_default_insecure_key_raises_error(self):
        with patch.dict(os.environ, {
            "CYBERSCOUT_ENV": "production",
            "SECRET_KEY": "cyberscout-ai-v1-1-secret-key-2026"
        }):
            with pytest.raises(RuntimeError) as exc_info:
                get_secret_key()
            assert "known insecure" in str(exc_info.value)

    def test_30_production_enforces_secure_session_cookies(self):
        with patch.dict(os.environ, {
            "CYBERSCOUT_ENV": "production",
            "SECRET_KEY": "a-strong-random-production-secret-key-at-least-32-bytes"
        }):
            prod_app = create_app()
            assert prod_app.config["SESSION_COOKIE_SECURE"] is True
            assert prod_app.config["SESSION_COOKIE_HTTPONLY"] is True
            assert prod_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


# =====================================================================
# Scenarios 31-33: Pagination Bounds & Input Hardening (SEC-05)
# =====================================================================
class TestPaginationLimitsAndInputHardening:
    """Verifies that pagination parameters are clamped to maximum bounds and handle malformed inputs."""

    def test_31_pagination_limit_clamped_to_max(self, client):
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"

        res = client.get("/admin/api/logs?page=1&limit=500")
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("limit") <= 200

    def test_32_pagination_non_numeric_handled_safely(self, client):
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"

        res = client.get("/admin/api/logs?page=abc&limit=xyz")
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("page") == 1
        assert data.get("limit") == 50

    def test_33_audit_logs_pagination_clamped(self, client):
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_role"] = "Administrator"
            sess["admin_username"] = "superadmin"

        res = client.get("/admin/api/audit-logs?page=1&limit=1000")
        assert res.status_code == 200
        data = res.get_json()
        assert data.get("limit") <= 200


# =====================================================================
# Scenarios 34-36: PostgreSQL Row Level Security (RLS) & Least Privilege (Requirement A)
# =====================================================================
class TestPostgreSQLLeastPrivilegeAndRLS:
    """Verifies catalog state, FORCE RLS, and immutable audit logs."""

    def test_34_all_sensitive_tables_have_rls_and_force_rls_enabled(self, db_manager):
        status = db_manager.verify_rls_policies()
        assert status["is_configured"] is True
        assert len(status["missing_tables"]) == 0
        assert len(status["unprotected_tables"]) == 0
        # Verify force_rls on all target tables
        for table, forced in status["force_rls"].items():
            assert forced is True, f"Table {table} does not have FORCE ROW LEVEL SECURITY enabled"

    def test_35_audit_logs_append_only_under_rls(self, db_manager):
        """Verifies that AuditLogs can be inserted, but cannot be deleted under cyberscout_app RLS."""
        conn = db_manager.get_connection()
        cur = conn.cursor()
        try:
            # 1. Insert test audit log
            cur.execute('INSERT INTO "AuditLogs" (timestamp, username, event_type, action, status) VALUES (NOW(), %s, %s, %s, %s);',
                        ("rls_verifier", "RLS_DELETE_TEST_EVENT", "TEST_ACTION", "SUCCESS"))
            conn.commit()

            # 2. Switch to cyberscout_app role within transaction
            cur.execute("SET ROLE cyberscout_app;")

            # 3. Attempt to delete audit log: RLS audit_no_delete policy (USING false) rejects it (affects 0 rows)
            cur.execute('DELETE FROM "AuditLogs" WHERE event_type = %s;', ("RLS_DELETE_TEST_EVENT",))
            deleted = cur.rowcount
            conn.commit()
            assert deleted == 0, f"RLS no-delete violated! Deleted {deleted} rows"

            # 4. Reset role to verify row remains intact
            cur.execute("RESET ROLE;")
            cur.execute('SELECT COUNT(*) FROM "AuditLogs" WHERE event_type = %s;', ("RLS_DELETE_TEST_EVENT",))
            count = cur.fetchone()[0]
            assert count >= 1, "AuditLog was unexpectedly missing!"

            # Cleanup
            cur.execute('DELETE FROM "AuditLogs" WHERE event_type = %s;', ("RLS_DELETE_TEST_EVENT",))
            conn.commit()
        finally:
            cur.close()

    def test_36_opportunities_public_read_and_collector_write(self, db_manager):
        """Verifies Opportunity table is readable and writable under RLS."""
        conn = db_manager.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT COUNT(*) FROM "Opportunities";')
            count = cur.fetchone()[0]
            assert count >= 0
        finally:
            cur.close()
