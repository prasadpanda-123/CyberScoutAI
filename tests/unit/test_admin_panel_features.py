"""
Unit and Integration Tests for Admin Panel Controls & User Management CRUD.
"""

import unittest
from dashboard.app import create_app
from src.database.user_repository import UserRepository
from src.database.admin_repository import AdminRepository
from src.database.connection import DatabaseManager


class TestAdminPanelFeatures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.u_repo = UserRepository(cls.db_manager)
        cls.a_repo = AdminRepository(cls.db_manager)
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()
        self.csrf_token = "admin-test-csrf-token"
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Admin"
            sess["admin_csrf_token"] = self.csrf_token
            sess["user_csrf_token"] = self.csrf_token

    def test_01_admin_users_get_default_users_tab(self):
        res = self.client.get("/admin/users")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Standard Users", html)
        self.assertIn("System Administrators", html)
        self.assertIn("panda", html)

    def test_02_admin_users_get_admins_tab(self):
        res = self.client.get("/admin/users?tab=admins")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("System Administrators", html)
        self.assertIn("admin", html)
        self.assertIn("YOU", html)

    def test_03_admin_cannot_lock_self(self):
        res = self.client.post(
            "/admin/users?tab=admins",
            data={
                "csrf_token": self.csrf_token,
                "action": "toggle_status",
                "target_type": "admin",
                "account_id": 1,
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("You cannot lock or deactivate your own administrative account", html)

    def test_04_admin_cannot_delete_self(self):
        res = self.client.post(
            "/admin/users?tab=admins",
            data={
                "csrf_token": self.csrf_token,
                "action": "delete_account",
                "target_type": "admin",
                "account_id": 1,
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("You cannot delete your own administrative account", html)

    def test_05_admin_can_toggle_and_delete_standard_user(self):
        temp_user = self.u_repo.create_user("dummy_test_sub", "dummy_sub@example.com", "DummyPass123!", role="Viewer")
        user_id = temp_user["id"]

        try:
            # 1. Lock user
            res = self.client.post(
                "/admin/users?tab=users",
                data={
                    "csrf_token": self.csrf_token,
                    "action": "toggle_status",
                    "target_type": "user",
                    "account_id": user_id,
                },
                follow_redirects=True,
            )
            self.assertEqual(res.status_code, 200)
            self.assertIn("locked successfully", res.get_data(as_text=True))

            # Verify in DB
            u = self.u_repo.get_by_id(user_id)
            self.assertEqual(u["is_active"], 0)

            # 2. Delete user
            del_res = self.client.post(
                "/admin/users?tab=users",
                data={
                    "csrf_token": self.csrf_token,
                    "action": "delete_account",
                    "target_type": "user",
                    "account_id": user_id,
                },
                follow_redirects=True,
            )
            self.assertEqual(del_res.status_code, 200)
            self.assertIn("deleted successfully", del_res.get_data(as_text=True))
            self.assertIsNone(self.u_repo.get_by_id(user_id))

        finally:
            self.u_repo.delete_user(user_id)

    def test_06_admin_scheduler_api_actions(self):
        headers = {
            "X-CSRF-Token": self.csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
        }

        # Pause scheduler
        pause_res = self.client.post("/admin/api/scheduler/pause", headers=headers)
        self.assertEqual(pause_res.status_code, 200)

        # Resume scheduler
        resume_res = self.client.post("/admin/api/scheduler/resume", headers=headers)
        self.assertEqual(resume_res.status_code, 200)

        # Restart scheduler
        restart_res = self.client.post("/admin/api/scheduler/restart", headers=headers)
        self.assertEqual(restart_res.status_code, 200)

    def test_07_admin_api_smtp_health_accepts_post_and_get(self):
        get_res = self.client.get("/admin/api/system/smtp-health")
        self.assertEqual(get_res.status_code, 200)

        post_res = self.client.post("/admin/api/system/smtp-health")
        self.assertEqual(post_res.status_code, 200)

    def test_08_admin_api_db_health_accepts_post_and_get(self):
        get_res = self.client.get("/admin/api/db/health")
        self.assertEqual(get_res.status_code, 200)

        post_res = self.client.post("/admin/api/db/health")
        self.assertEqual(post_res.status_code, 200)

    def test_09_admin_reports_page_renders_trigger_button(self):
        res = self.client.get("/admin/reports")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("btnGenReport", html)
        self.assertIn("triggerDailyReport", html)

    def test_10_admin_collectors_page_renders_trigger_button(self):
        res = self.client.get("/admin/collectors")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("btnTriggerScan", html)
        self.assertIn("triggerPipelineScan", html)


if __name__ == "__main__":
    unittest.main()
