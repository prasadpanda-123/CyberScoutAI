"""
User Repository for CyberScout AI Authentication and RBAC System.

Handles database persistence for user registration, authentication,
role management, and password updates.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
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
            user_id = row[0] if row else None
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

    def authenticate(self, identifier: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticates a user by email or username and password.
        Returns user dictionary if authentication succeeds and user is active.
        """
        clean_id = identifier.strip().lower()
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
                    "id": row_d.get("id"),
                    "username": row_d.get("username"),
                    "email": row_d.get("email"),
                    "role": row_d.get("role"),
                    "is_active": bool(row_d.get("is_active")),
                }
                self.update_last_login(row_d["id"])
                return user_dict
            return None
        finally:
            cursor.close()

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves user details by user_id."""
        sql = "SELECT id, username, email, role, is_active, created_at, last_login FROM Users WHERE id = ?"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()
            if row:
                return row_to_dict(row, cursor.description)
            return None
        finally:
            cursor.close()

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves user details by email."""
        sql = "SELECT id, username, email, role, is_active FROM Users WHERE LOWER(email) = ?"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                return row_to_dict(row, cursor.description)
            return None
        finally:
            cursor.close()

    def update_last_login(self, user_id: int) -> None:
        """Updates last_login timestamp for target user_id."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql = "UPDATE Users SET last_login = ? WHERE id = ?"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (ts, user_id))
            conn.commit()
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
            cursor.close()

    def has_users(self) -> bool:
        """Returns True if at least one user exists in the database."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM Users")
            res = cursor.fetchone()
            return res[0] > 0 if res else False
        finally:
            cursor.close()

    def has_admin(self) -> bool:
        """Returns True if at least one admin or super admin user exists."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM Users WHERE role IN ('Admin', 'Super Admin')")
            res = cursor.fetchone()
            return res[0] > 0 if res else False
        finally:
            cursor.close()
