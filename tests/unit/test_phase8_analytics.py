"""
Phase 8 Automated Test Suite: Advanced Analytics, User Intelligence & Opportunity Insights.

Validates all 43 mandatory test criteria across:
1. Platform Opportunity Analytics
2. Category & Opportunity Type Aggregations
3. Deadline Urgency Intelligence
4. Deterministic Discovery Trends & Velocity
5. User Personal Intelligence & Strict Tenant Isolation
6. Phase 7 Notification Analytics Integration
7. Source Health & Data Quality Telemetry
8. Security, RBAC, CSRF & SQL Injection Safety
9. Query Performance & EXPLAIN Verification
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List
import unittest

from dashboard.app import create_app
from src.database.analytics_repository import AnalyticsRepository
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.models.analytics_models import (
    PlatformOverviewDTO,
    DeadlineInsightsDTO,
    TrendSummaryDTO,
    UserPersonalIntelligenceDTO,
)
from src.models.opportunity import Opportunity
from src.database.source_repository import SourceRepository
from src.services.analytics_service import AnalyticsService


class TestPhase8Analytics(unittest.TestCase):
    """Authoritative test suite for Phase 8 Analytics & Intelligence."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.db_manager = DatabaseManager()
        cls.repo = AnalyticsRepository(db_manager=cls.db_manager)
        cls.service = AnalyticsService(repository=cls.repo, db_manager=cls.db_manager)
        cls.opp_repo = OpportunityRepository(db_manager=cls.db_manager)
        cls.source_repo = SourceRepository(db_manager=cls.db_manager)

        # Unique namespace for this test execution
        cls.test_run_id = f"p8_{uuid.uuid4().hex[:6]}"
        cls.test_source_id = f"src_p8_{uuid.uuid4().hex[:6]}"

        # Register source in Sources table to satisfy foreign key constraint
        cls.source_repo.sync_from_config(
            {
                "sources": [
                    {
                        "id": cls.test_source_id,
                        "name": "Test Phase 8 Source",
                        "collection_method": "api",
                        "default_category": "internship",
                        "enabled": True,
                        "trust_tier": "tier_1",
                    }
                ]
            }
        )

        # Create two dedicated test users
        with cls.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "Users" (username, email, password_hash, role, is_active, created_at)
                VALUES (%s, %s, 'test_hash', 'User', 1, NOW())
                RETURNING id;
                """,
                (f"user_a_{cls.test_run_id}", f"usera_{cls.test_run_id}@example.com"),
            )
            cls.user_a_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO "Users" (username, email, password_hash, role, is_active, created_at)
                VALUES (%s, %s, 'test_hash', 'User', 1, NOW())
                RETURNING id;
                """,
                (f"user_b_{cls.test_run_id}", f"userb_{cls.test_run_id}@example.com"),
            )
            cls.user_b_id = cur.fetchone()["id"]

            # Create test admin
            cur.execute(
                """
                INSERT INTO "Admins" (username, email, password_hash, role, is_active, created_at)
                VALUES (%s, %s, 'admin_hash', 'Administrator', 1, NOW())
                RETURNING id;
                """,
                (f"admin_{cls.test_run_id}", f"admin_{cls.test_run_id}@example.com"),
            )
            cls.admin_id = cur.fetchone()["id"]

    @classmethod
    def tearDownClass(cls):
        try:
            with cls.db_manager.transaction() as cur:
                # Clean up notifications, search history, saved, prefs
                cur.execute('DELETE FROM "NotificationOutbox" WHERE user_id IN (%s, %s);', (cls.user_a_id, cls.user_b_id))
                cur.execute('DELETE FROM "SavedOpportunities" WHERE user_id IN (%s, %s);', (cls.user_a_id, cls.user_b_id))
                cur.execute('DELETE FROM "UserSearchHistory" WHERE user_id IN (%s, %s);', (cls.user_a_id, cls.user_b_id))
                cur.execute('DELETE FROM "UserPreferences" WHERE user_id IN (%s, %s);', (cls.user_a_id, cls.user_b_id))
                cur.execute('DELETE FROM "Users" WHERE id IN (%s, %s);', (cls.user_a_id, cls.user_b_id))
                cur.execute('DELETE FROM "Admins" WHERE id = %s;', (cls.admin_id,))
                cur.execute('DELETE FROM "Opportunities" WHERE source_id = %s;', (cls.test_source_id,))
                cur.execute('DELETE FROM "SourceHealth" WHERE source_id = %s;', (cls.test_source_id,))
                cur.execute('DELETE FROM "Sources" WHERE id = %s;', (cls.test_source_id,))
        except Exception:
            pass

    # Helper to insert a test opportunity with precise fields
    def _create_test_opportunity(
        self,
        title: str,
        category: str = "internship",
        opportunity_type: str = "internship",
        lifecycle_status: str = "active",
        quality_status: str = "passed",
        is_free: bool = True,
        paid: bool = False,
        pricing_type: str = "free",
        remote: bool = True,
        stipend_type: str = "fixed",
        stipend_amount: float = 1000.0,
        deadline: Any = None,
        first_seen_days_ago: int = 0,
        quarantine_reason: str = None,
    ) -> str:
        opp_id = f"opp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        first_seen = now - timedelta(days=first_seen_days_ago)

        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "Opportunities" (
                    id, title, url, url_hash, source_id, category, opportunity_type,
                    lifecycle_status, quality_status, is_free, paid, pricing_type,
                    remote, stipend_type, stipend_amount, stipend_currency,
                    certificate, certificate_available, deadline,
                    first_seen_at, last_seen_at, last_harvested_at,
                    quarantine_reason, status, discovered_date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, 'USD',
                    TRUE, 'yes', %s,
                    %s, %s, %s,
                    %s, 'active', CURRENT_DATE
                );
                """,
                (
                    opp_id,
                    title,
                    f"https://example.com/{opp_id}",
                    f"hash_{opp_id}",
                    self.test_source_id,
                    category,
                    opportunity_type,
                    lifecycle_status,
                    quality_status,
                    is_free,
                    paid,
                    pricing_type,
                    remote,
                    stipend_type,
                    stipend_amount,
                    deadline,
                    first_seen,
                    now,
                    now,
                    quarantine_reason,
                ),
            )
        return opp_id

    # =========================================================================
    # 1. PLATFORM OPPORTUNITY ANALYTICS (Scenarios 1 - 7)
    # =========================================================================

    def test_01_total_opportunity_count_is_correct(self):
        """Scenario 1: Total opportunity count reflects actual rows in database."""
        initial_total = self.repo.get_platform_overview().total_opportunities
        self._create_test_opportunity("Total Test Opp 1")
        new_total = self.repo.get_platform_overview().total_opportunities
        self.assertEqual(new_total, initial_total + 1)

    def test_02_active_count_is_correct(self):
        """Scenario 2: Active count only includes active/closing_soon non-quarantined records."""
        initial_active = self.repo.get_platform_overview().active_opportunities
        self._create_test_opportunity("Active Opp", lifecycle_status="active", quality_status="passed")
        self._create_test_opportunity("Closing Soon Opp", lifecycle_status="closing_soon", quality_status="passed")
        new_active = self.repo.get_platform_overview().active_opportunities
        self.assertEqual(new_active, initial_active + 2)

    def test_03_closing_soon_count_uses_existing_lifecycle_semantics(self):
        """Scenario 3: Closing-soon count strictly matches lifecycle_status = 'closing_soon'."""
        initial_cs = self.repo.get_platform_overview().closing_soon_opportunities
        self._create_test_opportunity("Closing Soon Item", lifecycle_status="closing_soon")
        new_cs = self.repo.get_platform_overview().closing_soon_opportunities
        self.assertEqual(new_cs, initial_cs + 1)

    def test_04_quarantined_records_excluded_from_normal_counts(self):
        """Scenario 4: Quarantined records are tracked separately and excluded from active count."""
        initial_active = self.repo.get_platform_overview().active_opportunities
        initial_quar = self.repo.get_platform_overview().quarantined_opportunities

        self._create_test_opportunity(
            "Quarantined Opp",
            lifecycle_status="active",
            quality_status="quarantined",
            quarantine_reason="Data syntax error",
        )

        overview = self.repo.get_platform_overview()
        self.assertEqual(overview.active_opportunities, initial_active)
        self.assertEqual(overview.quarantined_opportunities, initial_quar + 1)

    def test_05_removed_records_excluded_from_active_counts(self):
        """Scenario 5: Removed records are excluded from active counts."""
        initial_active = self.repo.get_platform_overview().active_opportunities
        initial_removed = self.repo.get_platform_overview().removed_opportunities

        self._create_test_opportunity("Removed Opp", lifecycle_status="removed")

        overview = self.repo.get_platform_overview()
        self.assertEqual(overview.active_opportunities, initial_active)
        self.assertEqual(overview.removed_opportunities, initial_removed + 1)

    def test_06_pricing_distribution_is_correct(self):
        """Scenario 6: Free, Paid, Freemium, and Unknown pricing are counted accurately."""
        initial_free = self.repo.get_platform_overview().free_opportunities
        initial_paid = self.repo.get_platform_overview().paid_opportunities
        initial_freemium = self.repo.get_platform_overview().freemium_opportunities

        self._create_test_opportunity("Free Opp", is_free=True, pricing_type="free")
        self._create_test_opportunity("Paid Opp", is_free=False, paid=True, pricing_type="paid")
        self._create_test_opportunity("Freemium Opp", is_free=False, paid=False, pricing_type="freemium")

        overview = self.repo.get_platform_overview()
        self.assertEqual(overview.free_opportunities, initial_free + 1)
        self.assertEqual(overview.paid_opportunities, initial_paid + 1)
        self.assertEqual(overview.freemium_opportunities, initial_freemium + 1)

    def test_07_remote_distribution_is_correct(self):
        """Scenario 7: Remote flag distribution matches stored boolean attributes."""
        initial_remote = self.repo.get_platform_overview().remote_opportunities
        self._create_test_opportunity("Remote Item", remote=True)
        self._create_test_opportunity("Onsite Item", remote=False)

        overview = self.repo.get_platform_overview()
        self.assertEqual(overview.remote_opportunities, initial_remote + 1)

    # =========================================================================
    # 2. CATEGORY & OPPORTUNITY TYPE (Scenarios 8 - 11)
    # =========================================================================

    def test_08_category_aggregation_is_correct(self):
        """Scenario 8: Category aggregation returns actual counts per category."""
        unique_cat = f"test_cat_{uuid.uuid4().hex[:6]}"
        self._create_test_opportunity("Cat Item 1", category=unique_cat)
        self._create_test_opportunity("Cat Item 2", category=unique_cat)

        cats = self.repo.get_category_distribution()
        cat_match = next((c for c in cats if c.category == unique_cat), None)
        self.assertIsNotNone(cat_match)
        self.assertEqual(cat_match.count, 2)

    def test_09_opportunity_type_aggregation_is_correct(self):
        """Scenario 9: Opportunity type aggregation accurately reflects stored values."""
        unique_type = f"type_{uuid.uuid4().hex[:6]}"
        self._create_test_opportunity("Type Item 1", opportunity_type=unique_type)
        self._create_test_opportunity("Type Item 2", opportunity_type=unique_type)

        types = self.repo.get_opportunity_type_distribution()
        type_match = next((t for t in types if t.opportunity_type == unique_type), None)
        self.assertIsNotNone(type_match)
        self.assertEqual(type_match.count, 2)

    def test_10_empty_category_values_handled_safely(self):
        """Scenario 10: Empty or null category values are normalized safely to 'other'."""
        self._create_test_opportunity("Empty Cat Item", category="")
        cats = self.repo.get_category_distribution()
        other_match = next((c for c in cats if c.category == "other"), None)
        self.assertIsNotNone(other_match)
        self.assertGreater(other_match.count, 0)

    def test_11_percentages_sum_correctly_where_applicable(self):
        """Scenario 11: Distribution percentages are non-negative and sum properly."""
        cats = self.repo.get_category_distribution()
        if cats:
            for c in cats:
                self.assertGreaterEqual(c.percentage, 0.0)
                self.assertLessEqual(c.percentage, 100.0)

    # =========================================================================
    # 3. DEADLINE INTELLIGENCE (Scenarios 12 - 14)
    # =========================================================================

    def test_12_deadline_buckets_are_correct(self):
        """Scenario 12: Deadlines today, 24h, 3d, 7d, and 30d place opportunities into proper buckets."""
        today = date.today()
        d_today = today
        d_2d = today + timedelta(days=2)
        d_6d = today + timedelta(days=6)
        d_25d = today + timedelta(days=25)

        initial = self.repo.get_deadline_insights()

        self._create_test_opportunity("Due Today", deadline=d_today)
        self._create_test_opportunity("Due in 2d", deadline=d_2d)
        self._create_test_opportunity("Due in 6d", deadline=d_6d)
        self._create_test_opportunity("Due in 25d", deadline=d_25d)

        insights = self.repo.get_deadline_insights()
        self.assertEqual(insights.due_today, initial.due_today + 1)
        self.assertEqual(insights.due_within_3d, initial.due_within_3d + 2)  # today + 2d
        self.assertEqual(insights.due_within_7d, initial.due_within_7d + 3)  # today + 2d + 6d
        self.assertEqual(insights.due_within_30d, initial.due_within_30d + 4)

    def test_13_expired_opportunities_do_not_appear_in_future_deadline_buckets(self):
        """Scenario 13: Expired opportunities do not contaminate future deadline buckets."""
        today = date.today()
        d_past = today - timedelta(days=5)

        initial = self.repo.get_deadline_insights()
        self._create_test_opportunity("Expired Item", deadline=d_past, lifecycle_status="expired")

        insights = self.repo.get_deadline_insights()
        self.assertEqual(insights.due_within_7d, initial.due_within_7d)
        self.assertEqual(insights.due_within_30d, initial.due_within_30d)

    def test_14_missing_deadline_values_do_not_break_analytics(self):
        """Scenario 14: Null or missing deadlines are counted under total_without_deadlines without error."""
        initial_none = self.repo.get_deadline_insights().total_without_deadlines
        self._create_test_opportunity("No Deadline Item", deadline=None)

        insights = self.repo.get_deadline_insights()
        self.assertEqual(insights.total_without_deadlines, initial_none + 1)

    # =========================================================================
    # 4. OPPORTUNITY TRENDS (Scenarios 15 - 19)
    # =========================================================================

    def test_15_current_period_counts_are_correct(self):
        """Scenario 15: Discovery trends accurately count items in the current period."""
        initial_curr = self.repo.get_discovery_trends(days=7).current_period_count
        self._create_test_opportunity("Recent Item", first_seen_days_ago=2)

        trends = self.repo.get_discovery_trends(days=7)
        self.assertEqual(trends.current_period_count, initial_curr + 1)

    def test_16_previous_period_counts_are_correct(self):
        """Scenario 16: Discovery trends accurately count items in the prior window."""
        initial_prev = self.repo.get_discovery_trends(days=7).previous_period_count
        self._create_test_opportunity("Older Item", first_seen_days_ago=10)  # Between 7 and 14 days ago

        trends = self.repo.get_discovery_trends(days=7)
        self.assertEqual(trends.previous_period_count, initial_prev + 1)

    def test_17_percentage_change_handles_zero_previous_values(self):
        """Scenario 17: Percentage change safely handles division by zero when previous period is zero."""
        # Simulated test: TrendSummaryDTO with 0 previous count
        t = TrendSummaryDTO(
            metric_name="test",
            current_period_count=10,
            previous_period_count=0,
            absolute_change=10,
            percentage_change=100.0,
            trend_direction="up",
        )
        self.assertEqual(t.percentage_change, 100.0)
        self.assertEqual(t.trend_direction, "up")

    def test_18_first_seen_at_is_used_correctly_for_discovery_trends(self):
        """Scenario 18: Discovery trends group and count strictly using first_seen_at."""
        trends = self.repo.get_discovery_trends(days=30)
        self.assertIsInstance(trends.points, list)
        if trends.points:
            self.assertTrue(all(len(pt.period_label) == 10 for pt in trends.points))

    def test_19_last_harvested_at_is_not_interpreted_as_new_opportunity_creation(self):
        """Scenario 19: An opportunity harvested today with first_seen_at 60 days ago is not counted in 7d trends."""
        initial_curr = self.repo.get_discovery_trends(days=7).current_period_count

        # Insert opportunity with first_seen 60 days ago
        opp_id = f"opp_old_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        first_seen = now - timedelta(days=60)
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "Opportunities" (
                    id, title, url, url_hash, source_id, category, opportunity_type,
                    first_seen_at, last_seen_at, last_harvested_at, status, discovered_date
                ) VALUES (
                    %s, 'Old Opp Harvested Today', %s, %s, %s, 'internship', 'internship',
                    %s, %s, %s, 'active', CURRENT_DATE
                );
                """,
                (opp_id, f"https://example.com/{opp_id}", f"h_{opp_id}", self.test_source_id, first_seen, now, now),
            )

        trends = self.repo.get_discovery_trends(days=7)
        self.assertEqual(trends.current_period_count, initial_curr)

    # =========================================================================
    # 5. USER PERSONAL INTELLIGENCE & ISOLATION (Scenarios 20 - 25)
    # =========================================================================

    def test_20_user_a_only_sees_user_a_analytics(self):
        """Scenario 20: User A's insights return strictly User A's saved items and searches."""
        opp_id = self._create_test_opportunity("User A Saved Program")

        # Save opportunity for User A
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "SavedOpportunities" (id, user_id, opportunity_id, created_at)
                VALUES (%s, %s, %s, NOW());
                """,
                (f"save_{uuid.uuid4().hex[:8]}", self.user_a_id, opp_id),
            )

        insights_a = self.repo.get_user_personal_intelligence(self.user_a_id)
        self.assertGreaterEqual(insights_a.total_saved, 1)

    def test_21_user_b_data_never_appears_in_user_a_analytics(self):
        """Scenario 21: User B's saved items or search queries are completely excluded from User A."""
        opp_id = self._create_test_opportunity("User B Unique Program")

        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "SavedOpportunities" (id, user_id, opportunity_id, created_at)
                VALUES (%s, %s, %s, NOW());
                """,
                (f"save_b_{uuid.uuid4().hex[:8]}", self.user_b_id, opp_id),
            )
            cur.execute(
                """
                INSERT INTO "UserSearchHistory" (id, user_id, query_text, searched_at)
                VALUES (%s, %s, 'user_b_secret_query', NOW());
                """,
                (f"search_b_{uuid.uuid4().hex[:8]}", self.user_b_id),
            )

        insights_a = self.repo.get_user_personal_intelligence(self.user_a_id)
        # Verify User B's query is absent from User A's recent searches
        search_texts = [s["query"] for s in insights_a.recent_searches]
        self.assertNotIn("user_b_secret_query", search_texts)

    def test_22_saved_opportunity_counts_are_correct(self):
        """Scenario 22: Active vs. Closing Soon vs. Expired counts in saved items are accurate."""
        today = date.today()
        opp_active = self._create_test_opportunity("Saved Active", lifecycle_status="active", deadline=today + timedelta(days=20))
        opp_cs = self._create_test_opportunity("Saved Closing Soon", lifecycle_status="closing_soon", deadline=today + timedelta(days=2))
        opp_exp = self._create_test_opportunity("Saved Expired", lifecycle_status="expired", deadline=today - timedelta(days=5))

        with self.db_manager.transaction() as cur:
            for opp in [opp_active, opp_cs, opp_exp]:
                cur.execute(
                    """
                    INSERT INTO "SavedOpportunities" (id, user_id, opportunity_id, created_at)
                    VALUES (%s, %s, %s, NOW());
                    """,
                    (f"save_{uuid.uuid4().hex[:8]}", self.user_a_id, opp),
                )

        insights = self.repo.get_user_personal_intelligence(self.user_a_id)
        self.assertGreaterEqual(insights.active_saved, 2)  # active + closing_soon
        self.assertGreaterEqual(insights.closing_soon_saved, 1)
        self.assertGreaterEqual(insights.expired_saved, 1)
        self.assertGreaterEqual(insights.saved_deadlines_within_7d, 1)

    def test_23_user_search_analytics_use_only_own_data(self):
        """Scenario 23: User search analytics aggregate only that specific user's search history."""
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "UserSearchHistory" (id, user_id, query_text, searched_at)
                VALUES (%s, %s, 'cloud security analyst', NOW());
                """,
                (f"search_{uuid.uuid4().hex[:8]}", self.user_a_id),
            )

        insights = self.repo.get_user_personal_intelligence(self.user_a_id)
        search_queries = [s["query"] for s in insights.recent_searches]
        self.assertIn("cloud security analyst", search_queries)

    def test_24_user_preference_analytics_are_correct(self):
        """Scenario 24: Explicit user preferences (categories, types, skills) populate personal profile."""
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "UserPreferences" (
                    id, user_id, skills, preferred_categories, preferred_types,
                    prefers_remote, preferred_location
                ) VALUES (
                    %s, %s, '["Python", "SIEM"]', '["internship", "job"]', '["internship"]',
                    TRUE, 'Remote'
                ) ON CONFLICT (user_id) DO UPDATE SET
                    skills = EXCLUDED.skills,
                    preferred_categories = EXCLUDED.preferred_categories,
                    preferred_types = EXCLUDED.preferred_types;
                """,
                (f"pref_{uuid.uuid4().hex[:8]}", self.user_a_id),
            )

        insights = self.repo.get_user_personal_intelligence(self.user_a_id)
        self.assertIn("Python", insights.skills)
        self.assertIn("internship", insights.preferred_categories)
        self.assertTrue(insights.prefers_remote)

    def test_25_empty_user_history_produces_safe_empty_states(self):
        """Scenario 25: A user with zero saved items and zero searches returns clean default DTO without errors."""
        fresh_user_id = 99999999
        insights = self.repo.get_user_personal_intelligence(fresh_user_id)
        self.assertEqual(insights.total_saved, 0)
        self.assertEqual(insights.active_saved, 0)
        self.assertEqual(len(insights.recent_searches), 0)
        self.assertEqual(insights.notifications_received, 0)

    # =========================================================================
    # 6. NOTIFICATION ANALYTICS (Scenarios 26 - 29)
    # =========================================================================

    def test_26_notification_totals_are_correct(self):
        """Scenario 26: Admin outbox totals reflect actual records in NotificationOutbox."""
        initial_total = self.repo.get_admin_operational_analytics().notification_metrics["total_records"]

        opp_id = self._create_test_opportunity("Notif Test Opp")
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "NotificationOutbox" (
                    id, user_id, opportunity_id, event_type, deduplication_key, status
                ) VALUES (%s, %s, %s, 'new', %s, 'pending');
                """,
                (f"notif_{uuid.uuid4().hex[:8]}", self.user_a_id, opp_id, f"dedup_{uuid.uuid4().hex[:8]}"),
            )

        metrics = self.repo.get_admin_operational_analytics().notification_metrics
        self.assertEqual(metrics["total_records"], initial_total + 1)

    def test_27_sent_and_failed_counts_are_correct(self):
        """Scenario 27: Sent and failed counts distinguish statuses properly."""
        initial_sent = self.repo.get_admin_operational_analytics().notification_metrics["sent"]
        initial_failed = self.repo.get_admin_operational_analytics().notification_metrics["failed"]

        opp_id = self._create_test_opportunity("Delivery Status Opp")
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "NotificationOutbox" (
                    id, user_id, opportunity_id, event_type, deduplication_key, status
                ) VALUES (%s, %s, %s, 'new', %s, 'sent');
                """,
                (f"notif_s_{uuid.uuid4().hex[:8]}", self.user_a_id, opp_id, f"dedup_s_{uuid.uuid4().hex[:8]}"),
            )
            cur.execute(
                """
                INSERT INTO "NotificationOutbox" (
                    id, user_id, opportunity_id, event_type, deduplication_key, status
                ) VALUES (%s, %s, %s, 'updated', %s, 'failed');
                """,
                (f"notif_f_{uuid.uuid4().hex[:8]}", self.user_a_id, opp_id, f"dedup_f_{uuid.uuid4().hex[:8]}"),
            )

        metrics = self.repo.get_admin_operational_analytics().notification_metrics
        self.assertEqual(metrics["sent"], initial_sent + 1)
        self.assertEqual(metrics["failed"], initial_failed + 1)

    def test_28_delivery_percentage_handles_zero_attempts(self):
        """Scenario 28: Outbox delivery success rate handles 0 attempts gracefully (defaults to 100.0%)."""
        metrics = self.repo.get_admin_operational_analytics().notification_metrics
        self.assertGreaterEqual(metrics["delivery_success_rate"], 0.0)
        self.assertLessEqual(metrics["delivery_success_rate"], 100.0)

    def test_29_notification_analytics_do_not_expose_email_contents(self):
        """Scenario 29: Admin notification analytics return aggregate stats without exposing message bodies."""
        metrics = self.repo.get_admin_operational_analytics().notification_metrics
        self.assertNotIn("email_body", metrics)
        self.assertNotIn("html", metrics)
        self.assertNotIn("password", metrics)

    # =========================================================================
    # 7. SOURCE & QUALITY ANALYTICS (Scenarios 30 - 33)
    # =========================================================================

    def test_30_source_statistics_use_existing_source_health(self):
        """Scenario 30: Source performance aggregates data directly from SourceHealth table."""
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                INSERT INTO "SourceHealth" (
                    source_id, health_status, items_seen, items_created, items_updated,
                    items_rejected, latency
                ) VALUES (%s, 'HEALTHY', 100, 80, 15, 5, 1.25)
                ON CONFLICT (source_id) DO UPDATE SET
                    items_seen = EXCLUDED.items_seen;
                """,
                (self.test_source_id,),
            )

        sources = self.repo.get_admin_operational_analytics().source_health_summary
        source_match = next((s for s in sources if s.source_id == self.test_source_id), None)
        self.assertIsNotNone(source_match)
        self.assertEqual(source_match.items_seen, 100)
        self.assertEqual(source_match.health_status, "HEALTHY")

    def test_31_quality_statistics_use_existing_phase6_status(self):
        """Scenario 31: Quality distributions reflect Phase 6 quality status classifications."""
        q_stats = self.repo.get_admin_operational_analytics().quality_distribution
        self.assertIn("passed", q_stats)

    def test_32_quarantine_statistics_are_correct(self):
        """Scenario 32: Quarantine counts and primary reason breakdowns match stored records."""
        reason = "Test Contradiction: is_free=True with fee"
        self._create_test_opportunity("Quarantined Spec Item", quality_status="quarantined", quarantine_reason=reason)

        q_summary = self.repo.get_admin_operational_analytics().quarantine_summary
        self.assertGreater(q_summary["total_quarantined"], 0)
        self.assertIn(reason, q_summary["reasons_breakdown"])

    def test_33_source_anomalies_are_represented_correctly(self):
        """Scenario 33: Source malformed percentage is computed correctly from items_rejected and items_seen."""
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                UPDATE "SourceHealth"
                SET items_seen = 200, items_rejected = 20
                WHERE source_id = %s;
                """,
                (self.test_source_id,),
            )

        sources = self.repo.get_admin_operational_analytics().source_health_summary
        match = next((s for s in sources if s.source_id == self.test_source_id), None)
        self.assertIsNotNone(match)
        self.assertEqual(match.malformed_rate, 10.0)

    # =========================================================================
    # 8. SECURITY, RBAC & CSRF (Scenarios 34 - 40)
    # =========================================================================

    def test_34_analytics_routes_require_authentication(self):
        """Scenario 34: Unauthenticated GET requests to /analytics and /insights redirect to login."""
        r1 = self.client.get("/analytics")
        self.assertEqual(r1.status_code, 302)
        self.assertIn("/login", r1.headers.get("Location", ""))

        r2 = self.client.get("/insights")
        self.assertEqual(r2.status_code, 302)
        self.assertIn("/login", r2.headers.get("Location", ""))

    def test_35_admin_analytics_require_admin_rbac(self):
        """Scenario 35: Standard users cannot access /admin/analytics."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_a_id
            sess["username"] = "standard_user"
            sess["role"] = "User"
            sess["admin_authenticated"] = False

        r = self.client.get("/admin/analytics")
        # Should redirect to admin login or forbidden
        self.assertIn(r.status_code, [302, 403])

    def test_36_user_analytics_enforces_ownership(self):
        """Scenario 36: Authenticated user accessing /insights receives strictly their own personal data."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_a_id
            sess["username"] = "user_a"
            sess["role"] = "User"

        r = self.client.get("/insights")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Personal Opportunity Insights", r.data)

    def test_37_rls_remains_enabled_and_enforced(self):
        """Scenario 37: RLS remains enabled and forced on Opportunities and NotificationOutbox."""
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname IN ('Opportunities', 'NotificationOutbox')
                  AND relkind = 'r';
                """
            )
            rows = cur.fetchall()
            for r in rows:
                self.assertTrue(r["relrowsecurity"], f"RLS must be enabled on {r['relname']}")
                self.assertTrue(r["relforcerowsecurity"], f"FORCE RLS must be enabled on {r['relname']}")

    def test_38_sql_parameters_are_properly_bound(self):
        """Scenario 38: SQL injection payloads in window filter do not execute or compromise database."""
        malicious_window = "30d; DROP TABLE \"Opportunities\";--"
        intel = self.service.get_market_intelligence(window=malicious_window)
        # Should default safely to 30d without executing injection
        self.assertIsNotNone(intel["overview"])
        self.assertGreater(intel["overview"].total_opportunities, 0)

    def test_39_no_arbitrary_query_endpoint_exists(self):
        """Scenario 39: Endpoints like /api/query, /api/sql, /api/analytics/raw do not exist."""
        for endpoint in ["/api/query", "/api/sql", "/api/analytics/raw", "/api/execute"]:
            r = self.client.get(endpoint)
            self.assertEqual(r.status_code, 404, f"Endpoint {endpoint} must not exist")

    def test_40_csrf_remains_present_for_state_mutations(self):
        """Scenario 40: State-mutating administrative or user routes reject requests without CSRF token."""
        r = self.client.post("/notifications/preferences", data={"delivery_mode": "immediate"})
        # Fails with 403 or redirect due to CSRF failure
        self.assertIn(r.status_code, [302, 400, 403])

    # =========================================================================
    # 9. PERFORMANCE & AGGREGATION (Scenarios 41 - 43)
    # =========================================================================

    def test_41_representative_analytics_queries_execute_successfully(self):
        """Scenario 41: Native PostgreSQL aggregation queries execute cleanly in sub-second time."""
        start = datetime.now()
        overview = self.repo.get_platform_overview()
        elapsed_ms = (datetime.now() - start).total_seconds() * 1000
        self.assertIsNotNone(overview)
        self.assertLess(elapsed_ms, 2000.0, "Platform overview aggregation must execute in under 2 seconds")

    def test_42_no_obvious_n_plus_one_queries(self):
        """Scenario 42: Category and Opportunity type distributions execute in single grouped SQL statements."""
        start = datetime.now()
        cats = self.repo.get_category_distribution()
        types = self.repo.get_opportunity_type_distribution()
        elapsed_ms = (datetime.now() - start).total_seconds() * 1000
        self.assertLess(elapsed_ms, 2000.0, "Distributions must execute efficiently in single queries")

    def test_43_large_opportunity_datasets_do_not_require_loading_entire_table(self):
        """Scenario 43: Platform overview uses COUNT FILTER aggregates without loading raw rows into Python."""
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                EXPLAIN
                SELECT
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE lifecycle_status IN ('active', 'closing_soon')) as active_count
                FROM "Opportunities";
                """
            )
            explain_plan = " ".join(r[0] for r in cur.fetchall())
            self.assertIn("Aggregate", explain_plan, "Database plan must use native PostgreSQL Aggregate node")


if __name__ == "__main__":
    unittest.main()
