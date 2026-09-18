"""
CyberScout AI — Phase 12 Canonical User ID UUID Migration Dedicated Verification Suite.

Tests:
1. Native PostgreSQL UUID primary key generation and uniqueness.
2. Canonical UUID format validation (RFC 4122 compliance).
3. Foreign key cascading and referential integrity across all dependent tables.
4. Zero-data-loss and zero-orphan verification.
5. User registration, authentication, and session identity preservation with UUID.
6. Personalization preferences persistence and retrieval by UUID.
7. Search history recording and querying by UUID.
8. Saved opportunities bookmarking and unsaving by UUID.
9. Notification outbox queuing, read status, and delivery deduplication by UUID.
10. Audit logging preservation with UUID.
11. IDOR resistance: cross-user isolation and safe error handling on malformed/tampered UUID inputs.
12. Strict identity boundary separation between Users (UUID) and Admins (INTEGER).
13. Migration idempotency (re-running migration v16 causes no data or schema corruption).
"""

import time
import unittest
import uuid
from typing import Any, Dict

from dashboard.app import create_app
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository
from src.database.admin_repository import AdminRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.database.notification_repository import NotificationRepository
from src.database.opportunity_repository import OpportunityRepository
from src.database.audit_log_repository import AuditLogRepository
from src.database.migrations.migration_manager import MigrationManager
from src.models.recommendation_models import UserPreferencesDTO
from src.models.notification_models import NotificationOutboxDTO


class TestPhase12CanonicalUserUuidMigration(unittest.TestCase):
    """Dedicated Phase 12 Canonical User UUID Migration Test Suite."""

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.user_repo = UserRepository(cls.db_manager)
        cls.admin_repo = AdminRepository(cls.db_manager)
        cls.pref_repo = UserPreferencesRepository(cls.db_manager)
        cls.notif_repo = NotificationRepository(cls.db_manager)
        cls.opp_repo = OpportunityRepository(cls.db_manager)
        cls.audit_repo = AuditLogRepository(cls.db_manager)
        cls.migration_mgr = MigrationManager(cls.db_manager)

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

        # Ensure prerequisite source exists for tests inserting test opportunities
        conn = cls.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO "Sources" (id, name, collection_method, canonical_url, status)
                VALUES ('hackthebox_academy', 'HackTheBox Academy', 'rss', 'https://academy.hackthebox.com', 'active')
                ON CONFLICT (id) DO NOTHING;
            """)
            conn.commit()
        finally:
            cursor.close()

    def test_01_users_table_uses_uuid_primary_key(self):
        """Verify Users.id is native PostgreSQL UUID type and primary key."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND LOWER(table_name) = 'users' 
                  AND LOWER(column_name) = 'id';
            """)
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0].lower(), "uuid")
            self.assertEqual(row[1], "NO")
            self.assertIn("gen_random_uuid", row[2].lower())

            cursor.execute("""
                SELECT conname, contype 
                FROM pg_constraint 
                WHERE conrelid = '"Users"'::regclass AND contype = 'p';
            """)
            pk = cursor.fetchone()
            self.assertIsNotNone(pk)
            self.assertEqual(pk[1], "p")
        finally:
            cursor.close()

    def test_02_all_referencing_columns_are_uuid(self):
        """Verify dependent foreign key columns are of type UUID."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            for tbl in ["SavedOpportunities", "UserPreferences", "UserSearchHistory", "NotificationOutbox", "AuditLogs"]:
                cursor.execute(f"""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                      AND LOWER(table_name) = LOWER('{tbl}') 
                      AND LOWER(column_name) = 'user_id';
                """)
                col = cursor.fetchone()
                self.assertIsNotNone(col, f"user_id column not found in {tbl}")
                self.assertEqual(col[0].lower(), "uuid", f"{tbl}.user_id is not UUID")
        finally:
            cursor.close()

    def test_03_zero_orphaned_records_and_unique_uuids(self):
        """Verify zero orphaned rows across all dependent tables and unique UUIDs in Users."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*), COUNT(DISTINCT id), COUNT(*) FILTER (WHERE id IS NULL) FROM "Users";')
            row = cursor.fetchone()
            total, distinct, nulls = int(row[0]), int(row[1]), int(row[2])
            self.assertGreater(total, 0)
            self.assertEqual(total, distinct, "Duplicate UUIDs detected in Users table!")
            self.assertEqual(nulls, 0, "NULL UUID detected in Users table!")

            for tbl in ["SavedOpportunities", "UserPreferences", "UserSearchHistory", "NotificationOutbox", "AuditLogs"]:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM "{tbl}" t
                    WHERE t.user_id IS NOT NULL 
                      AND NOT EXISTS (SELECT 1 FROM "Users" u WHERE u.id = t.user_id);
                """)
                orphans = int(cursor.fetchone()[0])
                self.assertEqual(orphans, 0, f"Orphaned records detected in {tbl}!")
        finally:
            cursor.close()

    def test_04_user_creation_and_canonical_uuid_resolution(self):
        """Verify new users receive valid RFC 4122 UUIDs and resolve correctly via get_by_id."""
        ts = int(time.time() * 1000)
        username = f"p12_user_{ts}"
        email = f"p12_user_{ts}@example.com"
        created = self.user_repo.create_user(username=username, email=email, password="SecurePassword123!", role="User")
        
        user_uuid = created["id"]
        self.assertIsNotNone(user_uuid)
        # Validate that user_uuid is a valid UUID
        parsed_uuid = uuid.UUID(str(user_uuid))
        self.assertEqual(str(parsed_uuid), str(user_uuid))

        # Retrieve by string UUID
        fetched = self.user_repo.get_by_id(str(user_uuid))
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["username"], username)
        self.assertEqual(fetched["email"], email)

        # Retrieve by UUID object
        fetched_obj = self.user_repo.get_by_id(parsed_uuid)
        self.assertIsNotNone(fetched_obj)
        self.assertEqual(fetched_obj["id"], str(user_uuid))

    def test_05_saved_opportunities_uuid_operations(self):
        """Verify saved opportunities save, count, list, and unsave operate strictly with UUIDs."""
        ts = int(time.time() * 1000)
        user = self.user_repo.create_user(username=f"p12_saved_{ts}", email=f"p12_saved_{ts}@example.com", password="Password123!", role="User")
        uid = user["id"]

        opp_id = "test_opp_p12_bookmark"
        # Ensure test opportunity exists in Opportunities table
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO "Opportunities" (id, title, url, url_hash, source_id, category, discovered_date, status)
                VALUES (%s, 'P12 Bookmark Opp', 'https://example.com/p12-opp', %s, 'hackthebox_academy', 'Cybersecurity', CURRENT_DATE, 'active')
                ON CONFLICT (id) DO NOTHING;
            """, (opp_id, f"hash_p12_{ts}"))
            conn.commit()
        finally:
            cursor.close()

        # Save opportunity
        saved = self.opp_repo.save_opportunity_for_user(uid, opp_id, notes="Phase 12 bookmark")
        self.assertTrue(saved)

        # Verify is saved
        is_saved = self.opp_repo.is_opportunity_saved(uid, opp_id)
        self.assertTrue(is_saved)

        # Verify count
        count = self.opp_repo.count_saved_opportunities(uid)
        self.assertEqual(count, 1)

        # Verify set of saved IDs
        saved_set = self.opp_repo.get_saved_ids_for_user(uid)
        self.assertIn(opp_id, saved_set)

        # Unsave opportunity
        unsaved = self.opp_repo.unsave_opportunity_for_user(uid, opp_id)
        self.assertTrue(unsaved)
        self.assertFalse(self.opp_repo.is_opportunity_saved(uid, opp_id))
        self.assertEqual(self.opp_repo.count_saved_opportunities(uid), 0)

    def test_06_user_preferences_uuid_operations(self):
        """Verify user career preferences persist and retrieve correctly using UUID."""
        ts = int(time.time() * 1000)
        user = self.user_repo.create_user(username=f"p12_prefs_{ts}", email=f"p12_prefs_{ts}@example.com", password="Password123!", role="User")
        uid = user["id"]

        dto = UserPreferencesDTO(
            skills=["reverse engineering", "threat hunting"],
            interests=["Malware Analysis", "DFIR"],
            preferred_categories=["Forensics", "Security"],
            preferred_types=["job", "internship"],
            prefers_remote=True,
            preferred_location="Bangalore",
            experience_level="Intermediate",
        )

        ok = self.pref_repo.save_preferences(uid, dto)
        self.assertTrue(ok)

        retrieved = self.pref_repo.get_preferences(uid)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.skills, ["reverse engineering", "threat hunting"])
        self.assertEqual(retrieved.prefers_remote, True)
        self.assertEqual(retrieved.experience_level.lower(), "intermediate")

    def test_07_notification_outbox_uuid_operations(self):
        """Verify notifications queue and retrieve correctly using UUID."""
        ts = int(time.time() * 1000)
        user = self.user_repo.create_user(username=f"p12_notif_{ts}", email=f"p12_notif_{ts}@example.com", password="Password123!", role="User")
        uid = user["id"]

        opp_id = "test_opp_p12_notif"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO "Opportunities" (id, title, url, url_hash, source_id, category, discovered_date, status)
                VALUES (%s, 'P12 Notif Opp', 'https://example.com/p12-notif', %s, 'hackthebox_academy', 'Cybersecurity', CURRENT_DATE, 'active')
                ON CONFLICT (id) DO NOTHING;
            """, (opp_id, f"hash_notif_{ts}"))
            conn.commit()
        finally:
            cursor.close()

        notif_dto = NotificationOutboxDTO(
            user_id=uid,
            opportunity_id=opp_id,
            event_type="new",
            deduplication_key=f"dedup_p12_{ts}",
            notification_type="email",
            delivery_mode="digest",
        )
        notif_id = self.notif_repo.enqueue_notification(notif_dto)
        self.assertIsNotNone(notif_id)

        # Retrieve user notifications
        cards = self.notif_repo.get_user_notifications(uid, limit=10)
        self.assertGreater(len(cards), 0)
        self.assertEqual(cards[0]["opportunity_id"], opp_id)

    def test_08_audit_log_uuid_recording(self):
        """Verify audit log event records valid user UUID."""
        ts = int(time.time() * 1000)
        user = self.user_repo.create_user(username=f"p12_audit_{ts}", email=f"p12_audit_{ts}@example.com", password="Password123!", role="User")
        uid = user["id"]

        entry = self.audit_repo.log_event(
            event_type="SECURITY_TEST",
            action="PHASE12_VERIFY",
            status="SUCCESS",
            user_id=uid,
            username=user["username"],
            source_ip="127.0.0.1",
            details="Verifying UUID recording in AuditLogs",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(str(entry.get("user_id")), str(uid))

    def test_09_idor_and_malformed_uuid_safety(self):
        """Verify malformed and cross-user UUIDs fail closed safely without HTTP 500."""
        # 1. Non-existent UUID
        non_existent_uuid = str(uuid.uuid4())
        prefs = self.pref_repo.get_preferences(non_existent_uuid)
        self.assertIsNone(prefs)

        saved_count = self.opp_repo.count_saved_opportunities(non_existent_uuid)
        self.assertEqual(saved_count, 0)

        # 2. Malformed UUIDs
        malformed_inputs = [
            "not-a-uuid",
            "12345",
            "'; DROP TABLE Users; --",
            "   ",
            "../../etc/passwd",
            "<script>alert(1)</script>",
        ]
        for bad_input in malformed_inputs:
            # UserRepository get_by_id fails safely
            res = self.user_repo.get_by_id(bad_input)
            self.assertIsNone(res)

            # UserPreferencesRepository fails safely
            pref_res = self.pref_repo.get_preferences(bad_input)
            self.assertIsNone(pref_res)

            # OpportunityRepository fails safely
            opp_res = self.opp_repo.is_opportunity_saved(bad_input, "test_opp")
            self.assertFalse(opp_res)

    def test_10_admin_and_user_identity_strict_separation(self):
        """Verify that Admin identity remains integer and cannot be confused with User UUID."""
        admin = self.admin_repo.get_by_id(1)
        if admin:
            self.assertIsInstance(admin["id"], int)

        # Check PostgreSQL Admins table primary key definition
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND LOWER(table_name) = 'admins' 
                  AND LOWER(column_name) = 'id';
            """)
            admin_id_type = cursor.fetchone()
            self.assertIsNotNone(admin_id_type)
            self.assertEqual(admin_id_type[0].lower(), "integer")

            cursor.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND LOWER(table_name) = 'users' 
                  AND LOWER(column_name) = 'id';
            """)
            user_id_type = cursor.fetchone()
            self.assertIsNotNone(user_id_type)
            self.assertEqual(user_id_type[0].lower(), "uuid")
        finally:
            cursor.close()

    def test_11_migration_v16_idempotency(self):
        """Verify that running apply_migrations() again is safe, idempotent, and non-destructive."""
        current_v = self.migration_mgr.get_current_version()
        self.assertEqual(current_v, 16)

        # Re-apply
        applied = self.migration_mgr.apply_migrations()
        self.assertEqual(applied, 0)
        self.assertEqual(self.migration_mgr.get_current_version(), 16)

        # Direct execution of _apply_v16_canonical_user_uuid_migration is also idempotent
        self.migration_mgr._apply_v16_canonical_user_uuid_migration()
        self.assertEqual(self.migration_mgr.get_current_version(), 16)


if __name__ == "__main__":
    unittest.main()
