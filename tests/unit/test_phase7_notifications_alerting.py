"""
Phase 7 Automated Test Suite: Intelligent Alerting, Change Detection & User Notification Engine.

Comprehensive verification of:
1. IDEMPOTENCY (Scenarios 1-6)
2. CHANGE EVENTS (Scenarios 7-11)
3. QUALITY / LIFECYCLE SUPPRESSION (Scenarios 12-16)
4. USER ISOLATION & RLS (Scenarios 17-20)
5. EMAIL RENDERING & SAFETY (Scenarios 21-28)
6. DIGEST DELIVERY (Scenarios 29-33)
7. RETRY & FAILURE HANDLING (Scenarios 34-38)
8. NOTIFICATION PREFERENCES (Scenarios 39-42)
9. SECURITY & CSRF (Scenarios 43-46)
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch
import uuid

from src.database.connection import DatabaseManager
from src.database.notification_repository import NotificationRepository
from src.database.opportunity_repository import OpportunityRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.database.user_repository import UserRepository
from src.database.source_repository import SourceRepository
from src.models.enums import (
    NotificationEventType,
    NotificationStatus,
    NotificationDeliveryMode,
    NotificationChannel,
    LifecycleStatus,
    QualityStatus,
    FreshnessStatus,
    Status,
)
from src.models.opportunity import Opportunity
from src.models.notification_models import (
    NotificationOutboxDTO,
    NotificationCardDTO,
    MeaningfulChangeDTO,
)
from src.models.recommendation_models import UserPreferencesDTO
from src.intelligence.meaningful_change_evaluator import MeaningfulChangeEvaluator
from src.intelligence.notification_engine import NotificationEngine
from src.intelligence.quiet_hours import is_in_quiet_hours
from src.notifier.email_renderer import ModernEmailRenderer
from src.services.notification_service import NotificationService
from dashboard.app import create_app


class TestPhase7NotificationsAlerting(unittest.TestCase):
    """Exhaustive test suite verifying Phase 7 notification engine invariants."""

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.db_manager.initialize_database()
        cls.notif_repo = NotificationRepository(cls.db_manager)
        cls.opp_repo = OpportunityRepository(cls.db_manager)
        cls.pref_repo = UserPreferencesRepository(cls.db_manager)
        cls.user_repo = UserRepository(cls.db_manager)
        cls.source_repo = SourceRepository(cls.db_manager)

        # Register unique test source for test class run
        cls.test_source_id = f"test_p7_src_{uuid.uuid4().hex[:6]}"
        cls.source_repo.sync_from_config(
            {
                "sources": [
                    {
                        "id": cls.test_source_id,
                        "name": "Test Phase 7 Source",
                        "collection_method": "api",
                        "default_category": "internship",
                        "enabled": True,
                        "trust_tier": "tier_1",
                    }
                ]
            }
        )

        # Create two test users
        u_a = cls.user_repo.create_user(
            username=f"user_a_{uuid.uuid4().hex[:6]}",
            email=f"user_a_{uuid.uuid4().hex[:6]}@test.example",
            password="TestPassword123!",
        )
        cls.user_a_id = u_a["id"]

        u_b = cls.user_repo.create_user(
            username=f"user_b_{uuid.uuid4().hex[:6]}",
            email=f"user_b_{uuid.uuid4().hex[:6]}@test.example",
            password="TestPassword123!",
        )
        cls.user_b_id = u_b["id"]

        # Configure default preferences for test users
        cls.pref_repo.save_preferences(
            cls.user_a_id,
            UserPreferencesDTO(
                skills=["cybersecurity", "python", "siem"],
                interests=["threat-intelligence", "soc"],
                preferred_categories=["internship", "job", "hackathon"],
                email_notifications_enabled=True,
                in_app_notifications_enabled=True,
                notify_new_opportunities=True,
                notify_meaningful_updates=True,
                notify_reopened_opportunities=True,
                delivery_mode="IMMEDIATE",
                digest_frequency="DAILY",
                quiet_hours_enabled=False,
                timezone="UTC",
            ),
        )

        cls.pref_repo.save_preferences(
            cls.user_b_id,
            UserPreferencesDTO(
                skills=["cloud", "aws"],
                interests=["devsecops"],
                preferred_categories=["job"],
                email_notifications_enabled=True,
                in_app_notifications_enabled=True,
                notify_new_opportunities=True,
                notify_meaningful_updates=True,
                notify_reopened_opportunities=True,
                delivery_mode="DIGEST",
                digest_frequency="DAILY",
                quiet_hours_enabled=False,
                timezone="UTC",
            ),
        )

        cls.app = create_app(db_manager=cls.db_manager)
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def _save_opp(self, opp: Opportunity) -> Opportunity:
        """Persists opportunity in database so foreign key constraints on NotificationOutbox succeed."""
        opp.source_id = self.test_source_id
        self.opp_repo.save_or_update(opp)
        return opp

    def _ensure_opp_exists(self, opp_id: str, title: Optional[str] = None, category: str = "internship") -> Opportunity:
        """Helper to ensure an opportunity exists in Opportunities table for manual outbox insertion."""
        t = title or f"Test Opp {opp_id}"
        opp = Opportunity(
            id=opp_id,
            title=t,
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category=category,
            opportunity_type=category,
            tags=["cybersecurity", "python", "siem"],
            quality_status="passed",
            lifecycle_status="active",
        )
        self.opp_repo.save_or_update(opp)
        return opp

    def setUp(self):
        super().setUp()
        self._orig_init = NotificationEngine.__init__
        target_ids = [self.user_a_id, self.user_b_id]
        def _patched_init(engine_self, *args, **kwargs):
            if "target_user_ids" not in kwargs or kwargs["target_user_ids"] is None:
                kwargs["target_user_ids"] = target_ids
            self._orig_init(engine_self, *args, **kwargs)
        NotificationEngine.__init__ = _patched_init

    def tearDown(self):
        super().tearDown()
        NotificationEngine.__init__ = self._orig_init
        # Clean up notifications generated during tests for our test users
        try:
            with self.db_manager.transaction() as cur:
                cur.execute('DELETE FROM "NotificationOutbox" WHERE user_id IN (%s, %s);', (self.user_a_id, self.user_b_id))
        except Exception:
            pass

    # =========================================================================
    # 1. IDEMPOTENCY TESTS (Scenarios 1 - 6)
    # =========================================================================

    def test_01_new_opportunity_creates_one_notification(self):
        """Scenario 1: NEW opportunity creates exactly one notification row."""
        opp_id = f"test-p7-opp-1-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title=f"SOC Analyst Intern {uuid.uuid4().hex[:6]}",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="internship",
            opportunity_type="internship",
            description="SOC Analyst Internship with SIEM and Python",
            tags=["cybersecurity", "python", "siem"],
            quality_status="passed",
            lifecycle_status="active",
        )
        saved_opp = self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        created_count = engine.process_harvest_events(new_items=[saved_opp])

        self.assertGreaterEqual(created_count, 1)

        # Verify exactly one notification in outbox for user A
        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        matching = [n for n in notifications if n["opportunity_id"] == saved_opp.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["event_type"], "NEW")

    def test_02_reharvesting_unchanged_creates_zero_notifications(self):
        """Scenario 2: Re-harvesting unchanged opportunity produces 0 additional notifications."""
        opp_id = f"test-p7-opp-2-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Threat Intelligence Fellow",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="internship",
            opportunity_type="internship",
            description="Threat intel analysis with Python",
            tags=["cybersecurity", "python"],
            quality_status="passed",
            lifecycle_status="active",
        )
        self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        # Harvest 1: NEW
        engine.process_harvest_events(new_items=[opp])

        initial_count = len(self.notif_repo.get_user_notifications(self.user_a_id))

        # Harvest 2, 3, 4: UNCHANGED (no new or updated passed)
        c2 = engine.process_harvest_events(new_items=[], updated_items=[], reopened_items=[])
        c3 = engine.process_harvest_events(new_items=[], updated_items=[], reopened_items=[])
        c4 = engine.process_harvest_events(new_items=[], updated_items=[], reopened_items=[])

        self.assertEqual(c2, 0)
        self.assertEqual(c3, 0)
        self.assertEqual(c4, 0)

        # Count must remain unchanged
        final_count = len(self.notif_repo.get_user_notifications(self.user_a_id))
        self.assertEqual(initial_count, final_count)

    def test_03_repeated_scheduler_does_not_duplicate(self):
        """Scenario 3: Repeated scheduler runs with same opportunity never duplicate."""
        opp_id = f"test-p7-opp-3-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Incident Responder",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="job",
            opportunity_type="full_time",
            description="Incident response position",
            tags=["cybersecurity", "siem"],
            quality_status="passed",
            lifecycle_status="active",
        )
        saved_opp = self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        # Attempt to harvest same item as NEW repeatedly
        engine.process_harvest_events(new_items=[saved_opp])
        engine.process_harvest_events(new_items=[saved_opp])
        engine.process_harvest_events(new_items=[saved_opp])

        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        matching = [n for n in notifications if n["opportunity_id"] == saved_opp.id]
        self.assertEqual(len(matching), 1)

    def test_04_concurrent_notification_creation_no_duplicates(self):
        """Scenario 4: Concurrent notification creation does not create duplicates."""
        opp_id = f"test-p7-opp-4-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Penetration Tester",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="internship",
            opportunity_type="internship",
            description="Penetration testing with python",
            tags=["cybersecurity", "python"],
            quality_status="passed",
            lifecycle_status="active",
        )
        saved_opp = self._save_opp(opp)

        def _enqueue():
            eng = NotificationEngine(db_manager=self.db_manager)
            return eng.process_harvest_events(new_items=[saved_opp])

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_enqueue) for _ in range(5)]
            results = [f.result() for f in as_completed(futures)]

        # Across all concurrent attempts, exactly one notification row per user should exist
        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        matching = [n for n in notifications if n["opportunity_id"] == saved_opp.id]
        self.assertEqual(len(matching), 1)

    def test_05_same_event_cannot_be_queued_twice(self):
        """Scenario 5: Database constraint rejects identical deduplication key."""
        opp_id = f"test-p7-opp-5-{uuid.uuid4().hex[:8]}"
        self._ensure_opp_exists(opp_id)
        dedup_key = f"user:{self.user_a_id}:opp:{opp_id}:event:new"
        notif = NotificationOutboxDTO(
            user_id=self.user_a_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=dedup_key,
        )

        id1 = self.notif_repo.enqueue_notification(notif)
        self.assertIsNotNone(id1)

        # Enqueue second time with exact same dedup key -> must return None (ON CONFLICT DO NOTHING)
        id2 = self.notif_repo.enqueue_notification(notif)
        self.assertIsNone(id2)

    def test_06_restart_simulation_does_not_recreate_sent_events(self):
        """Scenario 6: Already-sent notification is not recreated or re-sent after restart."""
        opp_id = f"test-p7-opp-6-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="AppSec Specialist",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="job",
            opportunity_type="full_time",
            description="Application security role",
            tags=["cybersecurity", "python"],
            quality_status="passed",
            lifecycle_status="active",
        )
        saved_opp = self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        engine.process_harvest_events(new_items=[saved_opp])

        # Mark as SENT
        pending = self.notif_repo.get_pending_immediate()
        matching = [n for n in pending if n.opportunity_id == saved_opp.id and n.user_id == self.user_a_id]
        self.assertEqual(len(matching), 1)
        self.notif_repo.mark_sent(matching[0].id)

        # Restart simulation: re-process same opportunity
        engine2 = NotificationEngine(db_manager=self.db_manager)
        engine2.process_harvest_events(new_items=[saved_opp])

        # Must still be SENT and exactly 1 record
        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        recs = [n for n in notifications if n["opportunity_id"] == saved_opp.id]
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["status"], "SENT")

    # =========================================================================
    # 2. CHANGE EVENTS (Scenarios 7 - 11)
    # =========================================================================

    def test_07_meaningful_update_creates_update_event(self):
        """Scenario 7: Meaningful UPDATE (deadline extended) creates an update notification."""
        opp_id = f"test-p7-opp-7-{uuid.uuid4().hex[:8]}"
        opp_old = Opportunity(
            id=opp_id,
            title="Cyber Defense Internship",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="internship",
            deadline="2026-10-01",
            tags=["cybersecurity"],
            quality_status="passed",
            lifecycle_status="active",
        )
        opp_new = Opportunity(
            id=opp_id,
            title="Cyber Defense Internship",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="internship",
            deadline="2026-11-15",  # Changed deadline!
            tags=["cybersecurity"],
            quality_status="passed",
            lifecycle_status="active",
        )
        saved_new = self._save_opp(opp_new)
        opp_old.id = saved_new.id

        engine = NotificationEngine(db_manager=self.db_manager)
        engine.process_harvest_events(updated_items=[(saved_new, opp_old)])

        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        matching = [n for n in notifications if n["opportunity_id"] == saved_new.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["event_type"], "UPDATED")

    def test_08_non_meaningful_update_suppressed(self):
        """Scenario 8: Non-meaningful update (whitespace only) produces 0 notifications."""
        opp_id = f"test-p7-opp-8-{uuid.uuid4().hex[:8]}"
        opp_old = Opportunity(
            id=opp_id,
            title="Malware Analyst",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="job",
            description="Malware reverse engineering and static analysis.",
            tags=["cybersecurity"],
            quality_status="passed",
            lifecycle_status="active",
        )
        opp_new = Opportunity(
            id=opp_id,
            title="Malware Analyst",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="job",
            description="  Malware reverse engineering and static analysis.  \n",  # whitespace only!
            tags=["cybersecurity"],
            quality_status="passed",
            lifecycle_status="active",
        )
        self._save_opp(opp_new)

        evaluator = MeaningfulChangeEvaluator()
        change = evaluator.evaluate(opp_new, opp_old)
        self.assertFalse(change.is_meaningful)

        engine = NotificationEngine(db_manager=self.db_manager)
        created = engine.process_harvest_events(updated_items=[(opp_new, opp_old)])
        self.assertEqual(created, 0)

    def test_09_reopened_opportunity_creates_notification(self):
        """Scenario 9: REOPENED opportunity creates a notification preserving original ID."""
        opp_id = f"test-p7-opp-9-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Cryptographic Engineer",
            url=f"https://example.com/opp/{opp_id}",
            source_id=self.test_source_id,
            category="job",
            description="Applied cryptography and PKI engineering",
            tags=["cybersecurity", "python"],
            quality_status="passed",
            lifecycle_status="reopened",
        )
        saved_opp = self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        engine.process_harvest_events(reopened_items=[saved_opp])

        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        matching = [n for n in notifications if n["opportunity_id"] == saved_opp.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["event_type"], "REOPENED")
        self.assertEqual(matching[0]["opportunity_id"], saved_opp.id)

    def test_10_closed_does_not_create_notification(self):
        """Scenario 10: CLOSED opportunity does not create normal new notification."""
        opp_id = f"test-p7-opp-10-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Closed Security Role",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="job",
            quality_status="passed",
            lifecycle_status="closed",
        )
        self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        created = engine.process_harvest_events(new_items=[opp])
        self.assertEqual(created, 0)

    def test_11_removed_does_not_create_notification(self):
        """Scenario 11: REMOVED opportunity does not create normal new notification."""
        opp_id = f"test-p7-opp-11-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Removed Security Role",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="job",
            quality_status="passed",
            lifecycle_status="removed",
        )
        self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        created = engine.process_harvest_events(new_items=[opp])
        self.assertEqual(created, 0)

    # =========================================================================
    # 3. QUALITY & LIFECYCLE SUPPRESSION (Scenarios 12 - 16)
    # =========================================================================

    def test_12_quarantined_opportunity_cannot_generate_notification(self):
        """Scenario 12: QUARANTINED opportunity cannot generate normal alert."""
        opp_id = f"test-p7-opp-12-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Quarantined Suspicious Post",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="job",
            quality_status="quarantined",
            quarantine_reason="Missing description and suspicious URL",
            lifecycle_status="active",
        )
        self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        created = engine.process_harvest_events(new_items=[opp])
        self.assertEqual(created, 0)

    def test_13_severely_stale_opportunity_cannot_generate_notification(self):
        """Scenario 13: SEVERELY_STALE opportunity cannot generate recommendation alert."""
        opp_id = f"test-p7-opp-13-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Ancient Security Post",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="job",
            quality_status="severely_stale",
            lifecycle_status="active",
        )
        saved = self._save_opp(opp)

        engine = NotificationEngine(db_manager=self.db_manager)
        created = engine.process_harvest_events(new_items=[saved])
        self.assertEqual(created, 0)

    def test_14_removed_opportunity_cannot_generate_alert(self):
        """Scenario 14: Removed opportunity cannot generate new alert."""
        opp_id = f"test-p7-opp-14-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Takedown Post",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            lifecycle_status="removed",
        )
        self._save_opp(opp)
        engine = NotificationEngine(db_manager=self.db_manager)
        self.assertEqual(engine.process_harvest_events(new_items=[opp]), 0)

    def test_15_eligibility_filtering_works(self):
        """Scenario 15: Eligibility filtering suppresses opportunities user is ineligible for."""
        opp_id = f"test-p7-opp-15-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Senior Security Architect",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="job",
            difficulty="advanced",
            tags=["aws", "cloud"],
            quality_status="passed",
            lifecycle_status="active",
        )
        saved = self._save_opp(opp)

        # Set user B as beginner
        prefs_b = self.pref_repo.get_preferences(self.user_b_id)
        prefs_b.experience_level = "beginner"
        self.pref_repo.save_preferences(self.user_b_id, prefs_b)

        engine = NotificationEngine(db_manager=self.db_manager)
        engine.process_harvest_events(new_items=[saved])

        user_b_notifs = self.notif_repo.get_user_notifications(self.user_b_id)
        matching_b = [n for n in user_b_notifs if n["opportunity_id"] == saved.id]
        self.assertEqual(len(matching_b), 0)

    def test_16_phase6_suppression_intact(self):
        """Scenario 16: Phase 6 lifecycle and quality states preserve suppression."""
        for status in ("quarantined", "rejected"):
            opp_id = f"test-p7-suppress-{status}-{uuid.uuid4().hex[:6]}"
            opp = Opportunity(
                id=opp_id,
                title="Suppressed Post",
                url=f"https://example.com/{opp_id}",
                source_id="test_p7_src",
                quality_status=status,
                lifecycle_status="active",
            )
            self._save_opp(opp)
            engine = NotificationEngine(db_manager=self.db_manager)
            self.assertEqual(engine.process_harvest_events(new_items=[opp]), 0)

    # =========================================================================
    # 4. USER ISOLATION & RLS (Scenarios 17 - 20)
    # =========================================================================

    def test_17_user_a_cannot_see_user_b_notifications(self):
        """Scenario 17: User A cannot see User B's notifications."""
        opp_id = f"opp_priv_b_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif_b = NotificationOutboxDTO(
            user_id=self.user_b_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_b_id}:opp:{opp_id}:event:new",
        )
        self.notif_repo.enqueue_notification(notif_b)

        user_a_notifs = self.notif_repo.get_user_notifications(self.user_a_id)
        opp_ids_a = [n["opportunity_id"] for n in user_a_notifs]
        self.assertNotIn(opp_id, opp_ids_a)

    def test_18_user_a_cannot_mark_user_b_notification(self):
        """Scenario 18: User A cannot mark User B's notification as read."""
        opp_id = f"opp_priv_b_read_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif_b = NotificationOutboxDTO(
            user_id=self.user_b_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_b_id}:opp:{opp_id}:event:new",
        )
        notif_id = self.notif_repo.enqueue_notification(notif_b)
        self.assertIsNotNone(notif_id)

        # User A attempts to mark User B's notification as read
        success = self.notif_repo.mark_as_read(notif_id, user_id=self.user_a_id)
        self.assertFalse(success)

        # Verify still unread for User B
        b_notifs = self.notif_repo.get_user_notifications(self.user_b_id)
        target = next((n for n in b_notifs if n["id"] == notif_id), None)
        self.assertIsNotNone(target)
        self.assertFalse(target["is_read"])

    def test_19_rls_is_enforced_on_table(self):
        """Scenario 19: Row Level Security is active and forced on NotificationOutbox."""
        with self.db_manager.transaction() as cur:
            cur.execute("""
                SELECT relrowsecurity, relforcerowsecurity 
                FROM pg_class 
                WHERE relname = %s AND relkind = 'r';
            """, ("NotificationOutbox",))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertTrue(row[0], "NotificationOutbox must have relrowsecurity=True")
            self.assertTrue(row[1], "NotificationOutbox must have relforcerowsecurity=True")

    def test_20_missing_user_identity_fails_closed(self):
        """Scenario 20: Missing or invalid user identity fails closed."""
        res = self.notif_repo.get_user_notifications(user_id=99999999)
        self.assertEqual(res, [])
        mark_res = self.notif_repo.mark_as_read(notification_id="some-id", user_id=99999999)
        self.assertFalse(mark_res)

    # =========================================================================
    # 5. EMAIL RENDERING & SAFETY (Scenarios 21 - 28)
    # =========================================================================

    def test_21_html_email_renders_successfully(self):
        """Scenario 21: HTML email renders successfully with modern styling."""
        renderer = ModernEmailRenderer()
        card = NotificationCardDTO(
            opportunity_id="card-1",
            title="AI Security Engineer",
            organization="Anthropic",
            category="job",
            opportunity_type="full_time",
            deadline="2026-12-31",
            pricing="Free",
            stipend="$120,000",
            location="Remote",
            skills=["ai", "python"],
            view_url="https://example.com/opp/card-1",
            event_type=NotificationEventType.NEW,
            match_reasons=["Matches Cybersecurity", "Remote Available"],
        )
        html, text = renderer.render_immediate(card, recipient_name="Alice")
        self.assertIn("CYBERSCOUT", html)
        self.assertIn("AI Security Engineer", html)
        self.assertIn("Anthropic", html)
        self.assertIn("VIEW OPPORTUNITY", html)

    def test_22_plain_text_alternative_generated(self):
        """Scenario 22: Plain-text alternative is generated cleanly."""
        renderer = ModernEmailRenderer()
        card = NotificationCardDTO(
            opportunity_id="card-2",
            title="Cloud Security Analyst",
            organization="AWS",
            category="job",
            opportunity_type="full_time",
            deadline="2026-11-20",
            view_url="https://example.com/opp/card-2",
            event_type=NotificationEventType.NEW,
        )
        html, text = renderer.render_immediate(card)
        self.assertIn("CYBERSCOUT AI", text)
        self.assertIn("Cloud Security Analyst", text)
        self.assertIn("https://example.com/opp/card-2", text)

    def test_23_malicious_title_is_escaped(self):
        """Scenario 23: Malicious script tags in title are HTML-escaped."""
        renderer = ModernEmailRenderer()
        card = NotificationCardDTO(
            opportunity_id="card-xss-title",
            title="<script>alert('pwned')</script> Threat Analyst",
            organization="EvilCorp",
            category="job",
            opportunity_type="full_time",
            view_url="https://example.com/safe",
            event_type=NotificationEventType.NEW,
        )
        html, _ = renderer.render_immediate(card)
        self.assertNotIn("<script>alert('pwned')</script>", html)
        self.assertTrue(
            "&lt;script&gt;alert(&#39;pwned&#39;)&lt;/script&gt;" in html
            or "&lt;script&gt;alert(&#x27;pwned&#x27;)&lt;/script&gt;" in html
        )

    def test_24_malicious_description_is_escaped(self):
        """Scenario 24: Malicious img onerror payload is safely escaped."""
        renderer = ModernEmailRenderer()
        card = NotificationCardDTO(
            opportunity_id="card-xss-desc",
            title="Safe Title",
            organization="Org",
            category="job",
            opportunity_type="full_time",
            description='<img src="x" onerror="alert(1)">',
            view_url="https://example.com/safe",
            event_type=NotificationEventType.NEW,
        )
        html, _ = renderer.render_immediate(card)
        self.assertNotIn('<img src="x" onerror="alert(1)">', html)
        self.assertIn("&lt;img src=&quot;x&quot; onerror=&quot;alert(1)&quot;&gt;", html)

    def test_25_unsafe_url_is_rejected(self):
        """Scenario 25: Unsafe javascript: and data: URLs are rejected/neutralized."""
        renderer = ModernEmailRenderer()
        self.assertEqual(renderer._sanitize_url("javascript:alert(1)"), "#")
        self.assertEqual(renderer._sanitize_url("data:text/html,<script>"), "#")
        self.assertEqual(renderer._sanitize_url("vbscript:msgbox(1)"), "#")
        self.assertEqual(renderer._sanitize_url("https://safe.example.com"), "https://safe.example.com")

    def test_26_safe_cta_is_rendered(self):
        """Scenario 26: Safe HTTPS URL renders inside CTA button."""
        renderer = ModernEmailRenderer()
        card = NotificationCardDTO(
            opportunity_id="card-cta",
            title="Safe CTA Opp",
            organization="Org",
            category="job",
            opportunity_type="full_time",
            view_url="https://cyberscout.ai/opportunities/card-cta",
            event_type=NotificationEventType.NEW,
        )
        html, _ = renderer.render_immediate(card)
        self.assertIn('href="https://cyberscout.ai/opportunities/card-cta"', html)

    def test_27_empty_optional_fields_do_not_break_template(self):
        """Scenario 27: Missing optional fields render cleanly without errors."""
        renderer = ModernEmailRenderer()
        card = NotificationCardDTO(
            opportunity_id="card-sparse",
            title="Minimalist Opportunity",
            organization="",
            category="other",
            opportunity_type="",
            deadline=None,
            pricing=None,
            stipend=None,
            location=None,
            skills=[],
            view_url="https://example.com",
            event_type=NotificationEventType.NEW,
        )
        html, text = renderer.render_immediate(card)
        self.assertIn("Minimalist Opportunity", html)
        self.assertIn("Minimalist Opportunity", text)

    def test_28_large_descriptions_safely_truncated(self):
        """Scenario 28: Long descriptions are safely truncated with ellipsis."""
        renderer = ModernEmailRenderer()
        long_desc = "A" * 500
        truncated = renderer._clean_text(long_desc, max_len=100)
        self.assertLessEqual(len(truncated), 103)
        self.assertTrue(truncated.endswith("..."))

    # =========================================================================
    # 6. DIGEST DELIVERY (Scenarios 29 - 33)
    # =========================================================================

    def test_29_digest_contains_only_eligible_event_records(self):
        """Scenario 29: Digest contains only eligible pending records for the user."""
        opp_id = f"opp_dig_1_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif = NotificationOutboxDTO(
            user_id=self.user_b_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_b_id}:opp:{opp_id}:event:new",
        )
        self.notif_repo.enqueue_notification(notif)

        pending = self.notif_repo.get_pending_digest_for_user(self.user_b_id)
        opp_ids = [n.opportunity_id for n in pending]
        self.assertIn(opp_id, opp_ids)

    def test_30_digest_contains_no_duplicate_opportunities(self):
        """Scenario 30: Digest service deduplicates cards so an opp appears at most once."""
        card1 = NotificationCardDTO(
            opportunity_id="dup_opp",
            title="Title A",
            organization="Org",
            category="job",
            opportunity_type="job",
            view_url="https://example.com",
            event_type=NotificationEventType.NEW,
        )
        card2 = NotificationCardDTO(
            opportunity_id="dup_opp",  # Duplicate ID!
            title="Title A Updated",
            organization="Org",
            category="job",
            opportunity_type="job",
            view_url="https://example.com",
            event_type=NotificationEventType.UPDATED,
        )

        service = NotificationService(db_manager=self.db_manager)
        deduped = service._deduplicate_cards([card1, card2])
        self.assertEqual(len(deduped), 1)

    def test_31_already_sent_event_does_not_appear_in_digest(self):
        """Scenario 31: Already sent event does not appear in subsequent digest queries."""
        opp_id = f"opp_dig_sent_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif = NotificationOutboxDTO(
            user_id=self.user_b_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_b_id}:opp:{opp_id}:event:new",
        )
        notif_id = self.notif_repo.enqueue_notification(notif)
        self.notif_repo.mark_sent(notif_id)

        pending = self.notif_repo.get_pending_digest_for_user(self.user_b_id)
        opp_ids = [n.opportunity_id for n in pending]
        self.assertNotIn(opp_id, opp_ids)

    def test_32_multiple_new_opportunities_grouped_in_digest(self):
        """Scenario 32: Multiple new opportunities group into a single digest email."""
        renderer = ModernEmailRenderer()
        cards = [
            NotificationCardDTO(
                opportunity_id=f"card-{i}",
                title=f"Opp {i}",
                organization="Org",
                category="job",
                opportunity_type="full_time",
                view_url=f"https://example.com/{i}",
                event_type=NotificationEventType.NEW,
            )
            for i in range(3)
        ]
        html, text = renderer.render_digest(cards, recipient_name="Bob")
        self.assertIn("3 new opportunities matched to your interests", html)
        self.assertIn("Opp 0", html)
        self.assertIn("Opp 1", html)
        self.assertIn("Opp 2", html)

    def test_33_digest_does_not_include_unrelated_old_opportunities(self):
        """Scenario 33: Digest only queries pending events, not the full opps database."""
        pending = self.notif_repo.get_pending_digest_for_user(self.user_b_id)
        for item in pending:
            self.assertEqual(item.status, "pending")

    # =========================================================================
    # 7. RETRY & FAILURE HANDLING (Scenarios 34 - 38)
    # =========================================================================

    def test_34_failed_delivery_is_marked_failed(self):
        """Scenario 34: Failed delivery records error and increments attempt count."""
        opp_id = f"opp_fail_1_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif = NotificationOutboxDTO(
            user_id=self.user_a_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_a_id}:opp:{opp_id}:event:new",
        )
        notif_id = self.notif_repo.enqueue_notification(notif)
        self.notif_repo.mark_failed(notif_id, error="SMTP connection timeout", retryable=False)

        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        rec = next(n for n in notifications if n["id"] == notif_id)
        self.assertEqual(rec["status"], "FAILED")
        self.assertEqual(rec["attempt_count"], 1)
        self.assertIn("SMTP connection timeout", rec["last_error"])

    def test_35_retry_does_not_create_another_logical_event(self):
        """Scenario 35: Retry operates on the existing outbox record."""
        opp_id = f"opp_fail_2_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif = NotificationOutboxDTO(
            user_id=self.user_a_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_a_id}:opp:{opp_id}:event:new",
        )
        notif_id = self.notif_repo.enqueue_notification(notif)
        self.notif_repo.mark_failed(notif_id, error="Err 1")
        self.notif_repo.mark_failed(notif_id, error="Err 2")

        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        recs = [n for n in notifications if n["opportunity_id"] == opp_id]
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["attempt_count"], 2)

    def test_36_retry_count_is_bounded(self):
        """Scenario 36: Outbox lookup excludes records exceeding max_attempts."""
        opp_id = f"opp_fail_bounded_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif = NotificationOutboxDTO(
            user_id=self.user_a_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_a_id}:opp:{opp_id}:event:new",
        )
        notif_id = self.notif_repo.enqueue_notification(notif)

        # Fail 3 times (default max_attempts = 3)
        self.notif_repo.mark_failed(notif_id, error="Attempt 1")
        self.notif_repo.mark_failed(notif_id, error="Attempt 2")
        self.notif_repo.mark_failed(notif_id, error="Attempt 3")

        pending = self.notif_repo.get_pending_immediate(max_attempts=3)
        ids = [n.id for n in pending]
        self.assertNotIn(notif_id, ids)

    def test_37_successful_delivery_marked_correctly(self):
        """Scenario 37: Successful delivery marks SENT with timestamp."""
        opp_id = f"opp_success_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        notif = NotificationOutboxDTO(
            user_id=self.user_a_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_a_id}:opp:{opp_id}:event:new",
        )
        notif_id = self.notif_repo.enqueue_notification(notif)
        self.notif_repo.mark_sent(notif_id)

        notifications = self.notif_repo.get_user_notifications(self.user_a_id)
        rec = next(n for n in notifications if n["id"] == notif_id)
        self.assertEqual(rec["status"], "SENT")
        self.assertIsNotNone(rec["sent_at"])

    def test_38_delivery_failure_does_not_fail_harvesting(self):
        """Scenario 38: Email delivery exception does not corrupt pipeline harvesting."""
        from src.automation.pipeline import run_pipeline_once

        mock_collector = MagicMock()
        mock_collector.execute_plan.return_value = []

        mock_email = MagicMock()
        mock_email.send_daily_digest.side_effect = Exception("Brevo SMTP down")

        # Run pipeline with send_email=True and failing email client
        res = run_pipeline_once(
            send_email=True,
            db_manager=self.db_manager,
            collector_manager=mock_collector,
            email_client=mock_email,
        )
        # Harvesting completed despite email failure
        self.assertIn("run_id", res)
        self.assertIn(res["status"], ("success", "completed"))

    # =========================================================================
    # 8. NOTIFICATION PREFERENCES (Scenarios 39 - 42)
    # =========================================================================

    def test_39_disabled_email_prevents_delivery(self):
        """Scenario 39: If email notifications are disabled, no email is sent."""
        opp_id = f"opp_no_email_{uuid.uuid4().hex[:6]}"
        self._ensure_opp_exists(opp_id)

        # Disable email for User A
        prefs = self.pref_repo.get_preferences(self.user_a_id)
        prefs.email_notifications_enabled = False
        self.pref_repo.save_preferences(self.user_a_id, prefs)

        service = NotificationService(db_manager=self.db_manager)
        mock_sender = MagicMock()
        service.email_sender = mock_sender

        notif = NotificationOutboxDTO(
            user_id=self.user_a_id,
            opportunity_id=opp_id,
            event_type=NotificationEventType.NEW.value,
            deduplication_key=f"user:{self.user_a_id}:opp:{opp_id}:event:new",
        )
        self.notif_repo.enqueue_notification(notif)

        service.dispatch_pending()
        mock_sender.send.assert_not_called()

        # Restore
        prefs.email_notifications_enabled = True
        self.pref_repo.save_preferences(self.user_a_id, prefs)

    def test_40_disabled_update_notifications_suppress_update(self):
        """Scenario 40: If notify_meaningful_updates=False, update events are not enqueued."""
        prefs = self.pref_repo.get_preferences(self.user_a_id)
        prefs.notify_meaningful_updates = False
        self.pref_repo.save_preferences(self.user_a_id, prefs)

        opp_id = f"test-p7-opp-40-{uuid.uuid4().hex[:8]}"
        opp_old = Opportunity(id=opp_id, title="Title", url=f"https://example.com/opp/{opp_id}", source_id=self.test_source_id, deadline="2026-10-01", quality_status="passed", lifecycle_status="active")
        opp_new = Opportunity(id=opp_id, title="Title", url=f"https://example.com/opp/{opp_id}", source_id=self.test_source_id, deadline="2026-11-01", quality_status="passed", lifecycle_status="active")
        self._save_opp(opp_new)

        engine = NotificationEngine(db_manager=self.db_manager, target_user_ids=[self.user_a_id])
        created = engine.process_harvest_events(updated_items=[(opp_new, opp_old)], target_user_ids=[self.user_a_id])
        self.assertEqual(created, 0)

        # Restore
        prefs.notify_meaningful_updates = True
        self.pref_repo.save_preferences(self.user_a_id, prefs)

    def test_41_enabled_new_opportunity_notifications_work(self):
        """Scenario 41: Enabled new opportunity notifications successfully enqueue."""
        opp_id = f"test-p7-opp-41-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Junior SOC Analyst",
            url=f"https://example.com/opp/{opp_id}",
            source_id="test_p7_src",
            category="internship",
            opportunity_type="internship",
            tags=["cybersecurity", "siem"],
            quality_status="passed",
            lifecycle_status="active",
        )
        self._save_opp(opp)
        engine = NotificationEngine(db_manager=self.db_manager)
        created = engine.process_harvest_events(new_items=[opp])
        self.assertGreaterEqual(created, 1)

    def test_42_quiet_hours_evaluation(self):
        """Scenario 42: Quiet hours evaluation correctly identifies sleep windows."""
        # 22:00 to 08:00
        now_midnight = datetime(2026, 9, 15, 23, 30, tzinfo=timezone.utc)
        self.assertTrue(is_in_quiet_hours("22:00", "08:00", "UTC", now_utc=now_midnight))

        now_noon = datetime(2026, 9, 15, 12, 30, tzinfo=timezone.utc)
        self.assertFalse(is_in_quiet_hours("22:00", "08:00", "UTC", now_utc=now_noon))

    # =========================================================================
    # 9. SECURITY & CSRF (Scenarios 43 - 46)
    # =========================================================================

    def test_43_unauthorized_notification_access_redirects(self):
        """Scenario 43: Unauthenticated user accessing /notifications is redirected to login."""
        response = self.client.get("/notifications")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers.get("Location", ""))

    def test_44_csrf_protection_on_mark_read_and_preferences(self):
        """Scenario 44: Forged POST to /notifications/mark-read or /preferences fails without CSRF."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_a_id
            sess["user_csrf_token"] = "valid-token-123456"

        # POST without CSRF token
        res_read = self.client.post("/notifications/mark-read", json={"notification_id": "fake"})
        self.assertEqual(res_read.status_code, 403)

        res_pref = self.client.post("/notifications/preferences", data={"delivery_mode": "DIGEST"})
        # Should redirect with danger flash because of CSRF mismatch
        self.assertEqual(res_pref.status_code, 302)

    def test_45_admin_observability_requires_admin(self):
        """Scenario 45: Operational /admin/email requires admin RBAC."""
        # Regular user logged in
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_a_id
            sess["is_admin"] = False

        res = self.client.get("/admin/email")
        self.assertIn(res.status_code, (302, 403))

    def test_46_admin_observability_returns_accurate_stats(self):
        """Scenario 46: NotificationRepository observability stats accurately reflect outbox states."""
        stats = self.notif_repo.get_admin_observability_stats()
        self.assertIn("total", stats)
        self.assertIn("pending", stats)
        self.assertIn("sent", stats)
        self.assertIn("failed", stats)
        self.assertIn("recent_failures", stats)
        self.assertIsInstance(stats["recent_failures"], list)


if __name__ == "__main__":
    unittest.main()
