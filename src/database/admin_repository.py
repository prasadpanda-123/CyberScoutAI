"""
Admin Repository for CyberScout AI Administrator Authentication and Management.

Handles database persistence for administrative accounts in the Admins table.
Completely isolated from standard user registration and normal user authentication.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from src.database.connection import DatabaseManager
from src.database.base_repository import row_to_dict
from src.core.logging import get_logger

logger = get_logger(__name__)


class AdminRepository:
    """
    Repository for managing administrator accounts in the Admins table.
    """

    VALID_ROLES = {"Admin", "admin", "Super Admin", "Administrator"}

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def create_admin(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "Admin",
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Creates a new administrator account in the Admins table with PBKDF2 SHA-256 password hashing.
        """
        if not email or not isinstance(email, str) or not email.strip():
            raise ValueError("Email cannot be empty or null.")

        clean_email = email.strip().lower()
        if "@" not in clean_email or "." not in clean_email.split("@")[-1]:
            raise ValueError(f"Invalid email format: {email}")

        if not password or not isinstance(password, str) or not password.strip():
            raise ValueError("Password cannot be empty or null.")

        if not username or not isinstance(username, str) or not username.strip():
            raise ValueError("Username cannot be empty or null.")

        clean_role = role.strip() if role else "Admin"
        if clean_role not in self.VALID_ROLES:
            raise ValueError(f"Invalid administrator role '{clean_role}'. Must be one of {sorted(self.VALID_ROLES)}")

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        INSERT INTO "Admins" (username, email, password_hash, role, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                sql,
                (
                    username.strip(),
                    clean_email,
                    password_hash,
                    clean_role,
                    1 if is_active else 0,
                    ts,
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            admin_id = row[0] if row else None
            logger.info(f"Created administrator account '{username.strip()}' in Admins table.")
            return {
                "id": admin_id,
                "username": username.strip(),
                "email": clean_email,
                "role": clean_role,
                "is_active": is_active,
                "created_at": ts,
            }
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Administrator Username or Email already exists: {e}")
        finally:
            cursor.close()

    def authenticate(self, identifier: Optional[str], password: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Authenticates an administrator by email or username and password against the Admins table ONLY.
        Returns administrator dictionary if authentication succeeds and administrator is active.
        """
        if not identifier or not isinstance(identifier, str) or not password:
            return None

        clean_id = identifier.strip().lower()
        if not clean_id:
            return None
        sql = 'SELECT id, username, email, password_hash, role, is_active FROM "Admins" WHERE LOWER(email) = ? OR LOWER(username) = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (clean_id, clean_id))
            row = cursor.fetchone()
            if not row:
                return None

            row_d = row_to_dict(row, cursor.description)

            if not row_d.get("is_active"):
                return None

            if check_password_hash(row_d.get("password_hash", ""), password):
                admin_dict = {
                    "id": row_d.get("id"),
                    "username": row_d.get("username"),
                    "email": row_d.get("email"),
                    "role": row_d.get("role"),
                    "is_active": bool(row_d.get("is_active")),
                }
                self.update_last_login(row_d["id"])
                return admin_dict
            return None
        finally:
            conn.rollback()
            cursor.close()

    def get_by_id(self, admin_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves administrator details by admin_id."""
        sql = 'SELECT id, username, email, role, is_active, created_at, last_login FROM "Admins" WHERE id = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (admin_id,))
            row = cursor.fetchone()
            if row:
                return row_to_dict(row, cursor.description)
            return None
        finally:
            conn.rollback()
            cursor.close()

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves administrator details by email."""
        sql = 'SELECT id, username, email, role, is_active FROM "Admins" WHERE LOWER(email) = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                return row_to_dict(row, cursor.description)
            return None
        finally:
            conn.rollback()
            cursor.close()

    def update_last_login(self, admin_id: int) -> None:
        """Updates last_login timestamp for target admin_id in Admins table."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql = 'UPDATE "Admins" SET last_login = ? WHERE id = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (ts, admin_id))
            conn.commit()
        finally:
            cursor.close()

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves administrator details by username."""
        if not username or not isinstance(username, str):
            return None
        sql = 'SELECT id, username, email, role, is_active, created_at, last_login FROM "Admins" WHERE LOWER(username) = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (username.strip().lower(),))
            row = cursor.fetchone()
            if row:
                return row_to_dict(row, cursor.description)
            return None
        finally:
            conn.rollback()
            cursor.close()

    def verify_password(self, admin_id: int, password: str) -> bool:
        """
        Verifies whether submitted plaintext password matches the stored password_hash for admin_id in Admins table.
        """
        if not admin_id or not password or not isinstance(password, str):
            return False
        sql = 'SELECT id, password_hash, is_active FROM "Admins" WHERE id = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (admin_id,))
            row = cursor.fetchone()
            if not row:
                return False
            row_d = row_to_dict(row, cursor.description)
            if not row_d.get("is_active"):
                return False
            pw_hash = row_d.get("password_hash")
            if not pw_hash:
                return False
            return check_password_hash(pw_hash, password)
        finally:
            conn.rollback()
            cursor.close()

    def update_password(self, admin_id: int, new_password: str) -> bool:
        """
        Updates administrator password with PBKDF2 SHA-256 hash after validating admin password complexity.
        """
        if not admin_id or not new_password or not isinstance(new_password, str):
            raise ValueError("Invalid admin_id or password.")
        if len(new_password) < 10:
            raise ValueError("Administrator password must be at least 10 characters long.")

        password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
        sql = 'UPDATE "Admins" SET password_hash = ? WHERE id = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (password_hash, admin_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Could not update administrator password: {e}")
        finally:
            cursor.close()

    def update_password_hash(self, admin_id: int, password_hash: str) -> bool:
        """
        Updates administrator password hash in Admins table directly.
        Used when password hash was precomputed after OTP verification.
        """
        if not admin_id or not password_hash or not isinstance(password_hash, str):
            raise ValueError("Invalid admin_id or password_hash.")
        sql = 'UPDATE "Admins" SET password_hash = ? WHERE id = ?'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (password_hash, admin_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Could not update administrator password hash: {e}")
        finally:
            cursor.close()

    def has_admin(self) -> bool:
        """Returns True if at least one admin user exists in the Admins table."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM "Admins"')
            res = cursor.fetchone()
            return res[0] > 0 if res else False
        finally:
            conn.rollback()
            cursor.close()

