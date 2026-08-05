"""
User Repository for CyberScout AI Authentication & RBAC System.

Manages user creation, authentication via password hashing, role permissions, and user lookup.
"""

from datetime import datetime, timezone
import sqlite3
from typing import Any, Dict, List, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from src.database.connection import DatabaseManager


class UserRepository:
    """
    Repository managing User entities in the SQLite Users table.
    """

    VALID_ROLES = ("Super Admin", "Administrator", "Operator", "Viewer")

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "Viewer",
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Creates a new user with password hashed using PBKDF2 SHA-256.
        """
        clean_role = role.strip()
        if clean_role not in self.VALID_ROLES:
            clean_role = "Viewer"

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        sql = """
        INSERT INTO Users (username, email, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                sql,
                (
                    username.strip(),
                    email.strip().lower(),
                    password_hash,
                    clean_role,
                    1 if is_active else 0,
                    ts,
                ),
            )
            conn.commit()
            user_id = cursor.lastrowid
            return {
                "id": user_id,
                "username": username,
                "email": email.lower(),
                "role": clean_role,
                "is_active": is_active,
                "created_at": ts,
            }
        except sqlite3.IntegrityError as e:
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

            if not row["is_active"]:
                return None

            if check_password_hash(row["password_hash"], password):
                user_dict = {
                    "id": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                    "role": row["role"],
                    "is_active": bool(row["is_active"]),
                }
                self.update_last_login(row["id"])
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
                return dict(row)
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
                return dict(row)
            return None
        finally:
            cursor.close()

    def update_last_login(self, user_id: int) -> None:
        """Updates last_login timestamp for target user_id."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql = "UPDATE Users SET last_login = ? WHERE id = ?"
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (ts, user_id))
        except Exception:
            pass

    def list_users(self) -> List[Dict[str, Any]]:
        """Lists all registered users."""
        sql = "SELECT id, username, email, role, is_active, created_at, last_login FROM Users ORDER BY id ASC"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            cursor.close()
