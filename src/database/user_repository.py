"""
User Repository for CyberScout AI Authentication and RBAC System.

Handles database persistence for user registration, authentication,
role management, and password updates.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from werkzeug.security import check_password_hash, generate_password_hash

from src.database.connection import DatabaseManager
from src.database.base_repository import row_to_dict


class UserRepository:
    """
    Repository for managing user accounts in the Users table.
    """

    VALID_ROLES = {"Admin", "User", "admin", "user", "Operator", "Viewer", "Super Admin", "Administrator"}

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    @staticmethod
    def _normalize_uid(user_id: Any) -> Optional[str]:
        """Validates and returns normalized canonical UUID string or None."""
        if not user_id:
            return None
        try:
            return str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return None

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "User",
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Creates a new user with password hashed using PBKDF2 SHA-256.
        """
        if not email or not isinstance(email, str) or not email.strip():
            raise ValueError("Email cannot be empty or null.")
        
        clean_email = email.strip().lower()
        if "@" not in clean_email or "." not in clean_email.split("@")[-1]:
            raise ValueError(f"Invalid email format: {email}")

        if not password or not isinstance(password, str) or not password.strip():
            raise ValueError("Password cannot be empty or null.")

        if len(password.strip()) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        if not username or not isinstance(username, str) or not username.strip():
            raise ValueError("Username cannot be empty or null.")

        clean_role = role.strip() if role else "User"
        if clean_role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role '{clean_role}'. Must be one of {sorted(self.VALID_ROLES)}")

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        INSERT INTO "Users" (username, email, password_hash, role, is_active, created_at)
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
            user_id = str(row[0]) if row and row[0] is not None else None
            return {
                "id": user_id,
                "username": username.strip(),
                "email": clean_email,
                "role": clean_role,
                "is_active": is_active,
                "created_at": ts,
            }
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Username or Email already exists: {e}")
        finally:
            cursor.close()

    def authenticate(self, identifier: Optional[str], password: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Authenticates a user by email or username and password.
        Returns user dictionary if authentication succeeds and user is active.
        """
        if not identifier or not isinstance(identifier, str) or not password:
            return None

        clean_id = identifier.strip().lower()
        if not clean_id:
            return None

        sql = "SELECT id, username, email, password_hash, role, is_active FROM Users WHERE LOWER(email) = ? OR LOWER(username) = ?"
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
                user_dict = {
                    "id": str(row_d.get("id")) if row_d.get("id") is not None else None,
                    "username": row_d.get("username"),
                    "email": row_d.get("email"),
                    "role": row_d.get("role"),
                    "is_active": bool(row_d.get("is_active")),
                }
                self.update_last_login(row_d["id"])
                return user_dict
            return None
        finally:
            conn.rollback()
            cursor.close()

    def get_by_id(self, user_id: Any) -> Optional[Dict[str, Any]]:
        """Retrieves user details by canonical user UUID."""
        uid = self._normalize_uid(user_id)
        if not uid:
            return None
        sql = 'SELECT id, username, email, role, is_active, created_at, last_login FROM "Users" WHERE id = %s'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (uid,))
            row = cursor.fetchone()
            if row:
                res = row_to_dict(row, cursor.description)
                if res.get("id"):
                    res["id"] = str(res["id"])
                return res
            return None
        finally:
            conn.rollback()
            cursor.close()

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves user details by username."""
        if not username or not isinstance(username, str):
            return None
        sql = 'SELECT id, username, email, role, is_active FROM "Users" WHERE LOWER(username) = %s'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (username.strip().lower(),))
            row = cursor.fetchone()
            if row:
                res = row_to_dict(row, cursor.description)
                if res.get("id"):
                    res["id"] = str(res["id"])
                return res
            return None
        finally:
            conn.rollback()
            cursor.close()

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves user details by email."""
        if not email or not isinstance(email, str):
            return None
        sql = 'SELECT id, username, email, role, is_active FROM "Users" WHERE LOWER(email) = %s'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                res = row_to_dict(row, cursor.description)
                if res.get("id"):
                    res["id"] = str(res["id"])
                return res
            return None
        finally:
            conn.rollback()
            cursor.close()

    def update_last_login(self, user_id: Any) -> None:
        """Updates last_login timestamp for target user UUID."""
        uid = self._normalize_uid(user_id)
        if not uid:
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql = 'UPDATE "Users" SET last_login = %s WHERE id = %s'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (ts, uid))
            conn.commit()
        finally:
            cursor.close()

    def verify_password(self, user_id: Any, password: str) -> bool:
        """
        Verifies whether submitted plaintext password matches the stored password_hash for user UUID.
        """
        uid = self._normalize_uid(user_id)
        if not uid or not password or not isinstance(password, str):
            return False
        sql = 'SELECT id, password_hash, is_active FROM "Users" WHERE id = %s'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (uid,))
            row = cursor.fetchone()
            if not row:
                return False
            row_d = row_to_dict(row, cursor.description)
            if not row_d.get("is_active"):  # Inactive user
                return False
            pw_hash = row_d.get("password_hash")
            if not pw_hash:
                return False
            return check_password_hash(pw_hash, password)
        finally:
            conn.rollback()
            cursor.close()

    def update_password(self, user_id: Any, new_password: str) -> bool:
        """
        Updates user password with PBKDF2 SHA-256 hash.
        """
        uid = self._normalize_uid(user_id)
        if not uid or not new_password or not isinstance(new_password, str):
            raise ValueError("Invalid user_id or password.")
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
        sql = 'UPDATE "Users" SET password_hash = %s WHERE id = %s'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (password_hash, uid))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Could not update password: {e}")
        finally:
            cursor.close()

    def update_password_hash(self, user_id: Any, password_hash: str) -> bool:
        """
        Updates user password hash in Users table directly with precomputed PBKDF2 hash.
        """
        uid = self._normalize_uid(user_id)
        if not uid or not password_hash or not isinstance(password_hash, str):
            raise ValueError("Invalid user_id or password_hash.")
        sql = 'UPDATE "Users" SET password_hash = %s WHERE id = %s'
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (password_hash, uid))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Could not update password hash: {e}")
        finally:
            cursor.close()

    def list_users(self) -> List[Dict[str, Any]]:
        """Lists all registered users."""
        sql = "SELECT id, username, email, role, is_active, created_at, last_login FROM Users ORDER BY id ASC"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [row_to_dict(r, cursor.description) for r in rows]
        finally:
            conn.rollback()
            cursor.close()

    def has_users(self) -> bool:
        """Returns True if at least one user exists in the database."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM "Users"')
            res = cursor.fetchone()
            return res[0] > 0 if res else False
        finally:
            conn.rollback()
            cursor.close()

    def has_admin(self) -> bool:
        """Returns True if at least one admin or super admin user exists."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM "Admins"')
            res = cursor.fetchone()
            if res and res[0] > 0:
                return True
            cursor.execute('SELECT COUNT(*) FROM "Users" WHERE role IN (\'Admin\', \'Super Admin\')')
            res_users = cursor.fetchone()
            return res_users[0] > 0 if res_users else False
        finally:
            conn.rollback()
            cursor.close()
