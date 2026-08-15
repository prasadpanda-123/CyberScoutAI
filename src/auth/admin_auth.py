"""
Admin Security Manager for CyberScout AI v2.2.

Provides password validation, rate limiting, account lockout, CSRF token management,
session regeneration, and audit logging hooks for the Administrative Portal.
"""

import datetime
import re
import secrets
from typing import Dict, Optional, Tuple

from src.database.audit_log_repository import AuditLogRepository
from src.database.user_repository import UserRepository


class AdminSecurityManager:
    """
    Manager for administrative security hardening rules.
    """

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    # Memory store for failed login tracking: key=(ip, username) -> list of datetime timestamps
    _failed_login_attempts: Dict[Tuple[str, str], list] = {}

    def __init__(
        self,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[AuditLogRepository] = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.audit_repo = audit_repo or AuditLogRepository()

    @classmethod
    def validate_password_strength(cls, password: str) -> Tuple[bool, str]:
        """
        Validates password strength for admin accounts.
        Rules:
        - At least 10 characters long
        - Contains at least 1 uppercase character
        - Contains at least 1 lowercase character
        - Contains at least 1 digit
        - Contains at least 1 special character
        """
        if len(password) < 10:
            return False, "Password must be at least 10 characters long."
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter."
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter."
        if not re.search(r"[0-9]", password):
            return False, "Password must contain at least one number."
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            return False, "Password must contain at least one special character (!@#$%^&*...)."
        return True, "Password is valid and strong."

    @classmethod
    def is_locked_out(cls, ip_address: str, username: str) -> bool:
        """
        Checks if target IP + username combination is locked out due to repeated failures.
        """
        key = (ip_address.strip(), username.strip().lower())
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(minutes=cls.LOCKOUT_DURATION_MINUTES)

        attempts = cls._failed_login_attempts.get(key, [])
        # Prune older attempts
        valid_attempts = [t for t in attempts if t > cutoff]
        cls._failed_login_attempts[key] = valid_attempts

        return len(valid_attempts) >= cls.MAX_FAILED_ATTEMPTS

    @classmethod
    def record_failed_attempt(cls, ip_address: str, username: str) -> None:
        """
        Records a failed login attempt for lockout tracking.
        """
        key = (ip_address.strip(), username.strip().lower())
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(minutes=cls.LOCKOUT_DURATION_MINUTES)

        attempts = cls._failed_login_attempts.get(key, [])
        valid_attempts = [t for t in attempts if t > cutoff]
        valid_attempts.append(now)
        cls._failed_login_attempts[key] = valid_attempts

    @classmethod
    def reset_failed_attempts(cls, ip_address: str, username: str) -> None:
        """
        Resets failed login attempt history upon successful authentication.
        """
        key = (ip_address.strip(), username.strip().lower())
        cls._failed_login_attempts.pop(key, None)

    @staticmethod
    def generate_csrf_token() -> str:
        """Generates a secure cryptographically random CSRF token."""
        return secrets.token_hex(32)

    @staticmethod
    def verify_csrf_token(session_token: Optional[str], form_token: Optional[str]) -> bool:
        """Validates submitted CSRF token against session token."""
        if not session_token or not form_token:
            return False
        return secrets.compare_digest(session_token, form_token)

    @staticmethod
    def generate_otp_code() -> str:
        """
        Generates a cryptographically secure 6-digit numeric OTP code.
        """
        return f"{secrets.randbelow(900000) + 100000:06d}"

    @staticmethod
    def hash_otp_code(otp_code: str) -> str:
        """
        Computes SHA-256 hash of target OTP code for secure storage.
        """
        import hashlib
        return hashlib.sha256(otp_code.encode("utf-8")).hexdigest()

    # Server-managed store for pending MFA OTP sessions: key=pending_token -> dict of MFA state
    _pending_mfa_sessions: Dict[str, dict] = {}

    @classmethod
    def store_pending_mfa(
        cls,
        user_id: int,
        username: str,
        email: str,
        role: str,
        otp_hash: str,
        expires_at: int,
        next_url: str = "",
    ) -> str:
        """
        Stores pending MFA OTP state in server memory and returns an opaque random pending token.
        Prevents sensitive OTP hashes from leaking into client-side session cookies.
        """
        pending_token = secrets.token_hex(32)
        cls._pending_mfa_sessions[pending_token] = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "otp_hash": otp_hash,
            "expires_at": expires_at,
            "attempts": 0,
            "next_url": next_url,
        }
        return pending_token

    @classmethod
    def get_pending_mfa(cls, pending_token: Optional[str]) -> Optional[dict]:
        """Retrieves pending MFA OTP state for a given pending token."""
        if not pending_token or not isinstance(pending_token, str):
            return None
        return cls._pending_mfa_sessions.get(pending_token)

    @classmethod
    def increment_pending_mfa_attempts(cls, pending_token: str) -> int:
        """Increments attempt count for target pending MFA session."""
        mfa_state = cls.get_pending_mfa(pending_token)
        if mfa_state is not None:
            mfa_state["attempts"] = mfa_state.get("attempts", 0) + 1
            return mfa_state["attempts"]
        return 0

    @classmethod
    def clear_pending_mfa(cls, pending_token: Optional[str]) -> None:
        """Removes pending MFA OTP state upon verification or expiration."""
        if pending_token and isinstance(pending_token, str):
            cls._pending_mfa_sessions.pop(pending_token, None)

