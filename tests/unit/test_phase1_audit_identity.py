"""
Unit tests for Phase 1 Audit Trail Correction & Identity Handling.
Validates:
1. Administrator audit events correctly record admin identity without FK errors or dropped IDs.
2. User audit events correctly record user UUID and satisfy PostgreSQL Users(id) FK constraint.
3. System-generated events (user_id=None or 'SYSTEM') log explicitly and cleanly.
4. Invalid/unresolved identity references are tracked safely in details without throwing exceptions.
5. Flexible log querying supports both user UUIDs and admin IDs.
6. Audit repository transaction failure handling and rollback behavior.
"""

import unittest
import uuid

from src.database.admin_repository import AdminRepository
from src.database.audit_log_repository import AuditLogRepository
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


class TestPhase1AuditIdentity(unittest.TestCase):
    """Test suite for AuditLogRepository polymorphic identity handling."""

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.audit_repo = AuditLogRepository(cls.db_manager)
        cls.user_repo = UserRepository(cls.db_manager)
        cls.admin_repo = AdminRepository(cls.db_manager)

        # Seed a dedicated test user
        cls.test_username = f"audit_u_{uuid.uuid4().hex[:6]}"
        cls.test_email = f"{cls.test_username}@example.com"
        u = cls.user_repo.create_user(
            username=cls.test_username,
            email=cls.test_email,
            password="UserComplexPass2026!",
            role="Viewer",
        )
        cls.user_id = str(u["id"])

        # Seed a dedicated test admin
        cls.test_admin_uname = f"audit_adm_{uuid.uuid4().hex[:6]}"
        cls.test_admin_email = f"{cls.test_admin_uname}@example.com"
        adm = cls.admin_repo.create_admin(
            username=cls.test_admin_uname,
            email=cls.test_admin_email,
            password="AdminComplexPass2026!",
            role="Super Admin",
        )
        cls.admin_id = int(adm["id"])

    def test_01_user_audit_event_records_uuid(self):
        """User action with valid user UUID records user_id and references Users table."""
        res = self.audit_repo.log_event(
            event_type="AUTH",
            action="USER_PROFILE_UPDATE",
            status="SUCCESS",
            user_id=self.user_id,
            username=self.test_username,
            source_ip="192.168.1.50",
            details="Profile preferences saved",
        )
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertEqual(res.get("user_id"), self.user_id)
        self.assertEqual(res.get("username"), self.test_username)

        # Query log by user_id
        logs = self.audit_repo.query_logs(user_id=self.user_id, event_type="AUTH")
        self.assertGreaterEqual(logs["total_records"], 1)
        actions = [log["action"] for log in logs["logs"]]
        self.assertIn("USER_PROFILE_UPDATE", actions)

    def test_02_admin_audit_event_records_admin_identity(self):
        """Admin action with integer admin ID records [admin_id: X] in details and maintains FK safety."""
        action_name = f"ADMIN_TEST_RUN_{uuid.uuid4().hex[:4]}"
        res = self.audit_repo.log_event(
            event_type="COLLECTORS",
            action=action_name,
            status="SUCCESS",
            user_id=self.admin_id,
            username=self.test_admin_uname,
            source_ip="10.0.0.1",
            details="Manual trigger initiated",
        )
        self.assertEqual(res.get("status"), "SUCCESS")
        # safe_user_id is None to satisfy fk_auditlogs_user_id -> Users(id)
        self.assertIsNone(res.get("user_id"))
        self.assertEqual(res.get("username"), self.test_admin_uname)
        self.assertIn(f"[admin_id: {self.admin_id}]", res.get("details", ""))

        # Query log by admin_id
        logs = self.audit_repo.query_logs(user_id=self.admin_id, event_type="COLLECTORS")
        self.assertGreaterEqual(logs["total_records"], 1)
        actions = [log["action"] for log in logs["logs"]]
        self.assertIn(action_name, actions)

    def test_03_admin_audit_event_with_string_id(self):
        """Admin action with string-formatted integer ID correctly resolves to admin record."""
        action_name = f"ADMIN_CONFIG_EDIT_{uuid.uuid4().hex[:4]}"
        res = self.audit_repo.log_event(
            event_type="CONFIG",
            action=action_name,
            status="SUCCESS",
            user_id=str(self.admin_id),
            source_ip="10.0.0.2",
            details="Settings updated",
        )
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn(f"[admin_id: {self.admin_id}]", res.get("details", ""))
        self.assertEqual(res.get("username"), self.test_admin_uname)

    def test_04_system_event_logs_explicitly(self):
        """System events with user_id=None or 'SYSTEM' record cleanly without unresolved warnings."""
        res = self.audit_repo.log_event(
            event_type="SCHEDULER",
            action="CRON_CYCLE_START",
            status="SUCCESS",
            user_id=None,
            username="SYSTEM",
            source_ip="127.0.0.1",
            details="Automated pipeline cycle initiated",
        )
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIsNone(res.get("user_id"))
        self.assertEqual(res.get("username"), "SYSTEM")
        self.assertNotIn("[unresolved", res.get("details", ""))

    def test_05_unresolved_user_uuid_logged_safely(self):
        """Non-existent user UUID is logged safely with [unresolved_user_id: ...] tag."""
        fake_uuid = str(uuid.uuid4())
        res = self.audit_repo.log_event(
            event_type="AUTH",
            action="PROBE_ORPHAN",
            status="FAILED",
            user_id=fake_uuid,
            username="OrphanProbe",
            details="Testing missing user",
        )
        self.assertEqual(res.get("status"), "FAILED")
        self.assertIsNone(res.get("user_id"))
        self.assertIn(f"[unresolved_user_id: {fake_uuid}]", res.get("details", ""))

    def test_06_unresolved_admin_id_logged_safely(self):
        """Non-existent integer admin ID is logged safely with [unresolved_admin_id: ...] tag."""
        non_existent_admin_id = 999999999
        res = self.audit_repo.log_event(
            event_type="AUTH",
            action="INVALID_ADMIN_ID",
            status="FAILED",
            user_id=non_existent_admin_id,
            details="Testing non-existent admin ID",
        )
        self.assertIsNone(res.get("user_id"))
        self.assertIn(f"[unresolved_admin_id: {non_existent_admin_id}]", res.get("details", ""))

    def test_07_audit_repo_handles_db_failure_safely(self):
        """Audit repository returns failure dictionary without crashing calling process on DB error."""
        from unittest.mock import patch
        with patch.object(self.db_manager, "transaction", side_effect=RuntimeError("Simulated DB Disk Full")):
            res = self.audit_repo.log_event(
                event_type="SYSTEM",
                action="FAILURE_TEST",
                status="FAILED",
                user_id=None,
                details="Test failure handling",
            )
            self.assertEqual(res.get("status"), "failed")
            self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
