"""
Unit tests for Admin Security Manager, Password Strength, Lockout, and Audit Logger.
"""

import pytest
from src.auth.admin_auth import AdminSecurityManager
from src.database.audit_log_repository import AuditLogRepository
from src.database.connection import DatabaseManager


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_admin_security.db"
    db_mgr = DatabaseManager(db_path=db_file)
    db_mgr.initialize_database()
    return db_mgr


def test_password_strength_validation():
    """Test password strength validation rules."""
    # Weak passwords
    ok, msg = AdminSecurityManager.validate_password_strength("short")
    assert not ok
    assert "at least 10 characters" in msg

    ok, msg = AdminSecurityManager.validate_password_strength("nouppercase123!")
    assert not ok
    assert "uppercase" in msg

    ok, msg = AdminSecurityManager.validate_password_strength("NOLOWERCASE123!")
    assert not ok
    assert "lowercase" in msg

    ok, msg = AdminSecurityManager.validate_password_strength("NoDigitsHere!")
    assert not ok
    assert "number" in msg

    ok, msg = AdminSecurityManager.validate_password_strength("NoSpecialChar123")
    assert not ok
    assert "special character" in msg

    # Strong password
    ok, msg = AdminSecurityManager.validate_password_strength("SecureP@ssw0rd2026!")
    assert ok
    assert "valid and strong" in msg


def test_rate_limiting_and_account_lockout():
    """Test login failure tracking and lockout logic."""
    ip = "192.168.1.100"
    user = "admin_test_lockout"

    AdminSecurityManager.reset_failed_attempts(ip, user)
    assert not AdminSecurityManager.is_locked_out(ip, user)

    for i in range(4):
        AdminSecurityManager.record_failed_attempt(ip, user)
        assert not AdminSecurityManager.is_locked_out(ip, user)

    # 5th failed attempt triggers lockout
    AdminSecurityManager.record_failed_attempt(ip, user)
    assert AdminSecurityManager.is_locked_out(ip, user)

    # Reset attempts unlocks account
    AdminSecurityManager.reset_failed_attempts(ip, user)
    assert not AdminSecurityManager.is_locked_out(ip, user)


def test_csrf_token_generation_and_verification():
    """Test CSRF token generation and validation."""
    token1 = AdminSecurityManager.generate_csrf_token()
    token2 = AdminSecurityManager.generate_csrf_token()

    assert len(token1) == 64
    assert token1 != token2

    assert AdminSecurityManager.verify_csrf_token(token1, token1)
    assert not AdminSecurityManager.verify_csrf_token(token1, token2)
    assert not AdminSecurityManager.verify_csrf_token(token1, None)


def test_otp_generation_and_verification():
    """Test 6-digit numeric OTP generation, hashing, and verification (Phases 6 & 7)."""
    otp = AdminSecurityManager.generate_otp_code()
    assert len(otp) == 6
    assert otp.isdigit()

    otp_hash = AdminSecurityManager.hash_otp_code(otp)
    assert len(otp_hash) == 64

    # Verify matching code
    assert AdminSecurityManager.verify_otp_code(otp, otp_hash)

    # Verify non-matching code
    assert not AdminSecurityManager.verify_otp_code("000000" if otp != "000000" else "999999", otp_hash)

    # Verify invalid format code (non-digit, short, long)
    assert not AdminSecurityManager.verify_otp_code("abc", otp_hash)
    assert not AdminSecurityManager.verify_otp_code("12345", otp_hash)
    assert not AdminSecurityManager.verify_otp_code("1234567", otp_hash)


def test_audit_log_repository(temp_db):
    """Test AuditLogRepository event creation and querying."""
    audit_repo = AuditLogRepository(db_manager=temp_db)

    # Use user_id=None since FK allows NULL for system-level events
    res = audit_repo.log_event(
        event_type="AUTH",
        action="ADMIN_LOGIN",
        status="SUCCESS",
        user_id=None,
        username="superadmin",
        source_ip="127.0.0.1",
        details="Login successful",
    )
    assert res.get("id") is not None or res.get("status") == "SUCCESS"

    logs_res = audit_repo.query_logs(event_type="AUTH", limit=500)
    assert logs_res["total_records"] >= 1
    assert any(log.get("action") == "ADMIN_LOGIN" for log in logs_res["logs"])
