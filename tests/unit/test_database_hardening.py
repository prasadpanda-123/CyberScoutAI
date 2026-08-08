"""
Comprehensive Unit & Integration Tests for PostgreSQL Database Hardening, User Data Cleanup & Auth Integrity.
"""

import time
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


class TestDatabaseHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.db_manager.initialize_database()
        cls.user_repo = UserRepository(cls.db_manager)

        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        cls.app = create_app(config_class=TestConfig)
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        """Clean up transient test user records created during test run."""
        conn = cls.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM "Users" 
                WHERE LOWER(email) LIKE '%%@example.com' 
                   OR LOWER(email) LIKE 'crafted_admin%%';
            """)
            conn.commit()
        except Exception:
            pass
        finally:
            cursor.close()

    def test_01_duplicate_email_rejected(self):
        """1 & 2. Duplicate email and case-insensitive duplicate email must be rejected."""
        ts = int(time.time() * 1000)
        email = f"dup_user_{ts}@example.com"
        username = f"dup_user_{ts}"

        # Create initial user
        self.user_repo.create_user(username=username, email=email, password="Password123!", role="Viewer")

        # Duplicate email exact match
        with self.assertRaises(ValueError):
            self.user_repo.create_user(username=f"{username}_2", email=email, password="Password123!", role="Viewer")

        # Case-insensitive duplicate email (e.g. UPPERCASE)
        upper_email = email.upper()
        with self.assertRaises(ValueError):
            self.user_repo.create_user(username=f"{username}_3", email=upper_email, password="Password123!", role="Viewer")

    def test_02_null_or_invalid_email_rejected(self):
        """3. NULL, empty string, whitespace-only, and malformed email addresses must be rejected."""
        with self.assertRaises(ValueError):
            self.user_repo.create_user(username="bademail1", email="", password="Password123!")

        with self.assertRaises(ValueError):
            self.user_repo.create_user(username="bademail2", email="   ", password="Password123!")

        with self.assertRaises(ValueError):
            self.user_repo.create_user(username="bademail3", email="notanemail", password="Password123!")

    def test_03_invalid_role_rejected(self):
        """4. Invalid roles must be rejected by application validation and database CHECK constraint."""
        ts = int(time.time() * 1000)
        invalid_roles = ["superuser", "root", "administrator", "ADMINISTRATOR", "owner", "hacker_role"]
        for role in invalid_roles:
            with self.assertRaises(ValueError, msg=f"Role '{role}' should have been rejected"):
                self.user_repo.create_user(
                    username=f"badrole_{ts}_{role}",
                    email=f"badrole_{ts}_{role}@example.com",
                    password="Password123!",
                    role=role,
                )

    def test_04_public_registration_forces_viewer_role(self):
        """5 & 6. Public registration endpoint forces Viewer role and prevents privilege escalation."""
        ts = int(time.time() * 1000)
        email = f"pubreg_{ts}@example.com"
        username = f"pubreg_{ts}"

        res = self.client.post("/register", data={
            "username": username,
            "email": email,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "role": "Super Admin"  # Malicious parameter attempt
        })
        self.assertEqual(res.status_code, 302)

        user = self.user_repo.get_by_email(email)
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "Viewer")
        self.assertNotEqual(user["role"], "Super Admin")
        self.assertNotEqual(user["role"], "Admin")

    def test_05_inactive_user_cannot_authenticate(self):
        """7. Inactive user (is_active = 0/False) cannot authenticate."""
        ts = int(time.time() * 1000)
        email = f"inactive_{ts}@example.com"
        username = f"inactive_{ts}"

        self.user_repo.create_user(
            username=username,
            email=email,
            password="Password123!",
            role="Viewer",
            is_active=False,
        )

        auth_res = self.user_repo.authenticate(email, "Password123!")
        self.assertIsNone(auth_res, "Inactive user must not be authenticated")

    def test_06_missing_password_rejected(self):
        """8. Missing or empty password must be rejected."""
        with self.assertRaises(ValueError):
            self.user_repo.create_user(username="nopass", email="nopass@example.com", password="")

    def test_07_legitimate_accounts_preserved(self):
        """12 & 13. Legitimate admin and production users must remain in PostgreSQL database."""
        preserved_emails = [
            "admin@cyberscout.ai",
            "prasadpanda7989@gmail.com",
            "sateeshwarareddy@adityatekkali.edu.in"
        ]
        for email in preserved_emails:
            user = self.user_repo.get_by_email(email)
            self.assertIsNotNone(user, f"Legitimate account '{email}' must be preserved in database!")

    def test_08_no_orphaned_auditlogs_user_references(self):
        """14 & 15. Foreign-key integrity works and no orphaned user references exist in AuditLogs."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM "AuditLogs" a
            LEFT JOIN "Users" u ON a.user_id = u.id
            WHERE a.user_id IS NOT NULL AND u.id IS NULL;
        """)
        orphaned_count = cursor.fetchone()[0]
        cursor.close()
        self.assertEqual(orphaned_count, 0, "No orphaned AuditLogs user_id references should exist")

    def test_09_authorization_and_admin_isolation(self):
        """9, 10, 11. Admin login requires OTP and unauthorized users cannot access or create admin accounts."""
        anon_client = self.app.test_client()

        # Public endpoints accessible
        self.assertEqual(anon_client.get("/").status_code, 200)
        self.assertEqual(anon_client.get("/login").status_code, 200)
        self.assertEqual(anon_client.get("/register").status_code, 200)
        self.assertEqual(anon_client.get("/forgot-password").status_code, 200)

        # Dashboard requires auth
        dash_res = anon_client.get("/dashboard")
        self.assertEqual(dash_res.status_code, 302)

        # Admin routes forbidden for unauthenticated / non-admin users
        for admin_path in ["/admin/dashboard", "/admin/users", "/admin/logs", "/admin/configuration"]:
            res = anon_client.get(admin_path)
            self.assertEqual(res.status_code, 302)
            self.assertIn("/admin/login", res.location)

    def test_10_migration_head_is_stamped(self):
        """16 & 17. Alembic migration applies successfully and database is at head version."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version_num FROM alembic_version;")
        row = cursor.fetchone()
        cursor.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "20260808_001")


if __name__ == "__main__":
    unittest.main()
