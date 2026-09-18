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

    _login_attempt_repo = None

    @classmethod
    def _get_login_repo(cls):
        if cls._login_attempt_repo is None:
            try:
                from src.database.login_attempt_repository import LoginAttemptRepository
                cls._login_attempt_repo = LoginAttemptRepository()
            except Exception as e:
                logger.warning(f"Could not initialize LoginAttemptRepository: {e}")
        return cls._login_attempt_repo

    @classmethod
    def is_locked_out(cls, ip_address: str, username: str, attempt_type: str = "admin_login") -> bool:
        """
        Checks if target IP + username combination is locked out due to repeated failures.
        Uses distributed PostgreSQL repository with safe fallback.
        """
        repo = cls._get_login_repo()
        if repo:
            try:
                return repo.is_locked_out(
                    ip_address=ip_address,
                    identifier=username,
                    attempt_type=attempt_type,
                    max_attempts=cls.MAX_FAILED_ATTEMPTS,
                    window_minutes=cls.LOCKOUT_DURATION_MINUTES,
                )
            except Exception as e:
                logger.warning(f"Error querying distributed lockout repository: {e}")

        # In-memory fallback
        key = (ip_address.strip(), username.strip().lower(), attempt_type)
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(minutes=cls.LOCKOUT_DURATION_MINUTES)

        attempts = cls._failed_login_attempts.get(key, [])
        valid_attempts = [t for t in attempts if t > cutoff]
        cls._failed_login_attempts[key] = valid_attempts

        return len(valid_attempts) >= cls.MAX_FAILED_ATTEMPTS

    @classmethod
    def record_failed_attempt(cls, ip_address: str, username: str, attempt_type: str = "admin_login") -> None:
        """
        Records a failed login attempt for lockout tracking across distributed workers.
        """
        repo = cls._get_login_repo()
        if repo:
            try:
                repo.record_failed_attempt(
                    ip_address=ip_address,
                    identifier=username,
                    attempt_type=attempt_type,
                )
            except Exception as e:
                logger.warning(f"Error recording failed attempt in distributed repository: {e}")

        key = (ip_address.strip(), username.strip().lower(), attempt_type)
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(minutes=cls.LOCKOUT_DURATION_MINUTES)

        attempts = cls._failed_login_attempts.get(key, [])
        valid_attempts = [t for t in attempts if t > cutoff]
        valid_attempts.append(now)
        cls._failed_login_attempts[key] = valid_attempts

    @classmethod
    def reset_failed_attempts(cls, ip_address: str, username: str, attempt_type: str = "admin_login") -> None:
        """
        Resets failed login attempt history upon successful authentication.
        """
        repo = cls._get_login_repo()
        if repo:
            try:
                repo.reset_failed_attempts(
                    ip_address=ip_address,
                    identifier=username,
                    attempt_type=attempt_type,
                )
            except Exception as e:
                logger.warning(f"Error resetting failed attempts in distributed repository: {e}")

        key = (ip_address.strip(), username.strip().lower(), attempt_type)
        cls._failed_login_attempts.pop(key, None)
        cls._failed_login_attempts.pop((ip_address.strip(), username.strip().lower()), None)

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
        Supports leading zeros (e.g. '012345') by zero-padding to exactly 6 digits.
        """
        return f"{secrets.randbelow(1000000):06d}"

    @staticmethod
    def hash_otp_code(otp_code: str) -> str:
        """
        Computes SHA-256 hash of target OTP code for secure storage.
        Normalizes by stripping any whitespace or formatting before hashing.
        """
        import hashlib
        import re
        clean_code = re.sub(r"[\s\-\u200b\u00a0\ufeff]", "", str(otp_code).strip())
        return hashlib.sha256(clean_code.encode("utf-8")).hexdigest()

    @classmethod
    def verify_otp_code(cls, otp_code: str, stored_otp_hash: str) -> bool:
        """
        Verifies whether submitted OTP code matches the stored OTP SHA-256 hash.
        Normalizes input (removes surrounding/internal whitespace, hyphens, zero-width chars)
        and validates length == 6 and digits-only before constant-time comparison.
        Uses constant-time comparison (secrets.compare_digest) to prevent timing attacks.
        """
        import hashlib
        import re
        if not otp_code or not stored_otp_hash or not isinstance(otp_code, str):
            return False
        clean_code = re.sub(r"[\s\-\u200b\u00a0\ufeff]", "", str(otp_code).strip())
        if len(clean_code) != 6 or not clean_code.isdigit():
            return False
        computed_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()
        return secrets.compare_digest(computed_hash, stored_otp_hash.strip())

    # Persistent repository reference for centralized PostgreSQL state
    _mfa_repo = None
    # Server-managed store for pending MFA OTP sessions fallback: key=pending_token -> dict of MFA state
    _pending_mfa_sessions: Dict[str, dict] = {}

    @classmethod
    def _get_mfa_repo(cls):
        """Lazy-instantiates MfaRepository connecting to PostgreSQL."""
        if cls._mfa_repo is None:
            try:
                from src.database.mfa_repository import MfaRepository
                cls._mfa_repo = MfaRepository()
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).debug(f"MfaRepository initialization deferred or fallback: {e}")
                return None
        return cls._mfa_repo

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
        Stores pending MFA OTP state in PostgreSQL (with server memory fallback)
        and returns an opaque random pending token.
        Prevents sensitive OTP hashes from leaking into client-side session cookies.
        """
        pending_token = secrets.token_hex(32)
        import time
        # Always maintain memory cache as resilient backup
        cls._pending_mfa_sessions[pending_token] = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": role,
            "otp_hash": otp_hash,
            "expires_at": expires_at,
            "attempts": 0,
            "next_url": next_url,
            "last_resend_at": int(time.time()),
        }

        repo = cls._get_mfa_repo()
        if repo:
            try:
                repo.store_pending_mfa(
                    token=pending_token,
                    user_id=user_id,
                    username=username,
                    email=email,
                    role=role,
                    otp_hash=otp_hash,
                    expires_at=expires_at,
                    next_url=next_url,
                )
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).warning(f"Failed to persist pending MFA in DB, falling back to memory: {e}")

        return pending_token

    @classmethod
    def update_pending_mfa_otp(cls, pending_token: str, new_otp_hash: str, new_expires_at: int) -> bool:
        """
        Updates the OTP hash and expiration for an existing pending MFA token (used for Resend OTP).
        Resets the attempt counter to 0.
        """
        if not pending_token or not isinstance(pending_token, str):
            return False
        import time
        now_ts = int(time.time())
        if pending_token in cls._pending_mfa_sessions:
            cls._pending_mfa_sessions[pending_token]["otp_hash"] = new_otp_hash
            cls._pending_mfa_sessions[pending_token]["expires_at"] = new_expires_at
            cls._pending_mfa_sessions[pending_token]["attempts"] = 0
            cls._pending_mfa_sessions[pending_token]["last_resend_at"] = now_ts

        repo = cls._get_mfa_repo()
        if repo:
            try:
                return repo.update_pending_mfa_otp(pending_token, new_otp_hash, new_expires_at)
            except Exception:
                return False
        return True

    @classmethod
    def get_pending_mfa(cls, pending_token: Optional[str]) -> Optional[dict]:
        """Retrieves pending MFA OTP state for a given pending token."""
        if not pending_token or not isinstance(pending_token, str):
            return None
        import time
        now_ts = int(time.time())

        repo = cls._get_mfa_repo()
        if repo:
            try:
                db_state = repo.get_pending_mfa(pending_token)
                if db_state is not None:
                    cls._pending_mfa_sessions[pending_token] = db_state
                    return db_state
                # If DB returned None (expired or cleared), purge from memory cache
                cls._pending_mfa_sessions.pop(pending_token, None)
                return None
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).debug(f"Failed to retrieve pending MFA from database: {e}")

        mem_state = cls._pending_mfa_sessions.get(pending_token)
        if mem_state:
            if now_ts > int(mem_state.get("expires_at", 0)):
                cls.clear_pending_mfa(pending_token)
                return None
            return mem_state

        return None

    @classmethod
    def increment_pending_mfa_attempts(cls, pending_token: str) -> int:
        """Increments attempt count for target pending MFA session."""
        if not pending_token or not isinstance(pending_token, str):
            return 0
        repo = cls._get_mfa_repo()
        if repo:
            try:
                attempts = repo.increment_pending_mfa_attempts(pending_token)
                if attempts > 0:
                    return attempts
            except Exception:
                pass
        mfa_state = cls._pending_mfa_sessions.get(pending_token)
        if mfa_state is not None:
            mfa_state["attempts"] = mfa_state.get("attempts", 0) + 1
            return mfa_state["attempts"]
        return 0

    @classmethod
    def clear_pending_mfa(cls, pending_token: Optional[str]) -> None:
        """Removes pending MFA OTP state upon verification or expiration."""
        if pending_token and isinstance(pending_token, str):
            repo = cls._get_mfa_repo()
            if repo:
                try:
                    repo.clear_pending_mfa(pending_token)
                except Exception:
                    pass
            cls._pending_mfa_sessions.pop(pending_token, None)

    # Server-managed store for pending password-change transactions fallback: key=pending_token -> dict
    _pending_pw_changes: Dict[str, dict] = {}

    @staticmethod
    def mask_email(email: Optional[str]) -> str:
        """
        Returns a masked representation of an email address (e.g. p***********@gmail.com).
        """
        if not email or "@" not in email:
            return "******@*******.***"
        local_part, domain = email.split("@", 1)
        if len(local_part) <= 2:
            masked_local = local_part[0] + "*"
        else:
            masked_local = local_part[0] + ("*" * (len(local_part) - 2)) + local_part[-1]
        return f"{masked_local}@{domain}"

    @classmethod
    def store_pending_password_change(
        cls,
        target_type: str,
        account_id: int,
        username: str,
        email: str,
        new_password_hash: str,
        otp_hash: str,
        expires_at: int,
    ) -> str:
        """
        Stores pending password change state in PostgreSQL (with server memory fallback).
        Never exposes plaintext passwords, password hashes, or OTP secrets to client cookies.
        """
        import time
        pending_token = secrets.token_hex(32)
        repo = cls._get_mfa_repo()
        if repo:
            try:
                return repo.store_pending_password_change(
                    token=pending_token,
                    target_type=target_type,
                    account_id=account_id,
                    username=username,
                    email=email,
                    new_password_hash=new_password_hash,
                    otp_hash=otp_hash,
                    expires_at=expires_at,
                )
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).warning(f"Failed to persist password change in DB, falling back to memory: {e}")

        cls._pending_pw_changes[pending_token] = {
            "target_type": target_type,
            "account_id": account_id,
            "username": username,
            "email": email,
            "new_password_hash": new_password_hash,
            "otp_hash": otp_hash,
            "expires_at": expires_at,
            "attempts": 0,
            "created_at": int(time.time()),
            "last_resend_at": int(time.time()),
        }
        return pending_token

    @classmethod
    def get_pending_password_change(cls, pending_token: Optional[str]) -> Optional[dict]:
        """Retrieves pending password change state for a given pending token."""
        if not pending_token or not isinstance(pending_token, str):
            return None
        repo = cls._get_mfa_repo()
        if repo:
            try:
                db_state = repo.get_pending_password_change(pending_token)
                if db_state is not None:
                    return db_state
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).debug(f"Failed to retrieve pending password change from DB: {e}")

        return cls._pending_pw_changes.get(pending_token)

    @classmethod
    def increment_pending_password_change_attempts(cls, pending_token: str) -> int:
        """Increments attempt counter for target pending password change transaction."""
        if not pending_token or not isinstance(pending_token, str):
            return 0
        repo = cls._get_mfa_repo()
        if repo:
            try:
                attempts = repo.increment_pending_password_change_attempts(pending_token)
                if attempts > 0:
                    return attempts
            except Exception:
                pass
        state = cls._pending_pw_changes.get(pending_token)
        if state is not None:
            state["attempts"] = state.get("attempts", 0) + 1
            return state["attempts"]
        return 0

    @classmethod
    def update_pending_password_change_otp(
        cls,
        pending_token: str,
        new_otp_hash: str,
        new_expires_at: int,
    ) -> bool:
        """Updates OTP hash and expiration upon resend request."""
        import time
        if not pending_token or not isinstance(pending_token, str):
            return False
        repo = cls._get_mfa_repo()
        if repo:
            try:
                ok = repo.update_pending_password_change_otp(pending_token, new_otp_hash, new_expires_at)
                if ok:
                    return True
            except Exception:
                pass
        state = cls._pending_pw_changes.get(pending_token)
        if state is not None:
            state["otp_hash"] = new_otp_hash
            state["expires_at"] = new_expires_at
            state["attempts"] = 0
            state["last_resend_at"] = int(time.time())
            return True
        return False

    @classmethod
    def clear_pending_password_change(cls, pending_token: Optional[str]) -> None:
        """Clears pending password change transaction upon completion, cancellation, or failure."""
        if pending_token and isinstance(pending_token, str):
            repo = cls._get_mfa_repo()
            if repo:
                try:
                    repo.clear_pending_password_change(pending_token)
                except Exception:
                    pass
            cls._pending_pw_changes.pop(pending_token, None)


