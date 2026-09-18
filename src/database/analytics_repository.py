"""
Analytics Repository for CyberScout AI.

Executes high-performance PostgreSQL 17 native aggregation queries to power
platform intelligence, market trends, user personal analytics, and administrative telemetry.
Adheres strictly to parameterized queries, zero-paid resources, and PostgreSQL RLS.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseManager
from src.models.analytics_models import (
    AdminAnalyticsOverviewDTO,
    CategoryDistributionItemDTO,
    DeadlineInsightsDTO,
    EconomicInsightsDTO,
    FreshnessInsightsDTO,
    OpportunityTypeDistributionItemDTO,
    PlatformOverviewDTO,
    SourceAnalyticsDTO,
    TrendPointDTO,
    TrendSummaryDTO,
    UserPersonalIntelligenceDTO,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


class AnalyticsRepository:
    """DAO providing pure SQL aggregations for CyberScout AI analytics."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    # =========================================================================
    # 1. PLATFORM OPPORTUNITY ANALYTICS
    # =========================================================================

    def get_platform_overview(self, days_limit: Optional[int] = None) -> PlatformOverviewDTO:
        """
        Calculates platform-wide aggregate counts and distributions using a single
        optimized SQL query.
        """
        sql = """
            SELECT
                COUNT(*) as total_count,
                COUNT(*) FILTER (WHERE lifecycle_status IN ('active', 'closing_soon') AND quality_status != 'quarantined') as active_count,
                COUNT(*) FILTER (WHERE lifecycle_status = 'closing_soon' AND quality_status != 'quarantined') as closing_soon_count,
                COUNT(*) FILTER (WHERE first_seen_at >= NOW() - INTERVAL '7 days' AND quality_status != 'quarantined') as new_week_count,
                COUNT(*) FILTER (WHERE first_seen_at >= NOW() - INTERVAL '30 days' AND quality_status != 'quarantined') as new_month_count,
                COUNT(*) FILTER (WHERE lifecycle_status = 'reopened' AND quality_status != 'quarantined') as reopened_count,
                COUNT(*) FILTER (WHERE lifecycle_status = 'expired') as expired_count,
                COUNT(*) FILTER (WHERE lifecycle_status = 'removed') as removed_count,
                COUNT(*) FILTER (WHERE quality_status = 'quarantined') as quarantined_count,
                COUNT(*) FILTER (WHERE is_free IS TRUE OR LOWER(pricing_type) = 'free') as free_count,
                COUNT(*) FILTER (WHERE paid IS TRUE OR LOWER(pricing_type) = 'paid') as paid_count,
                COUNT(*) FILTER (WHERE LOWER(pricing_type) = 'freemium') as freemium_count,
                COUNT(*) FILTER (WHERE (is_free IS NULL OR is_free IS FALSE) AND (paid IS NULL OR paid IS FALSE) AND (pricing_type IS NULL OR LOWER(pricing_type) IN ('unknown', ''))) as unknown_pricing_count,
                COUNT(*) FILTER (WHERE remote IS TRUE) as remote_count,
                COUNT(*) FILTER (WHERE LOWER(stipend_type) NOT IN ('none', '', 'unpaid') AND stipend_type IS NOT NULL) as stipend_count,
                COUNT(*) FILTER (WHERE certificate IS TRUE OR LOWER(certificate_available) = 'yes') as certificate_count
            FROM "Opportunities"
        """
        params: List[Any] = []
        if days_limit and days_limit > 0:
            sql += " WHERE first_seen_at >= NOW() - (%s * INTERVAL '1 day')"
            params.append(days_limit)

        with self.db_manager.transaction() as cur:
            cur.execute(sql, tuple(params))
            row = cur.fetchone()

        if not row:
            return PlatformOverviewDTO()

        return PlatformOverviewDTO(
            total_opportunities=row["total_count"] or 0,
            active_opportunities=row["active_count"] or 0,
            closing_soon_opportunities=row["closing_soon_count"] or 0,
            new_this_week_opportunities=row["new_week_count"] or 0,
            new_this_month_opportunities=row["new_month_count"] or 0,
            reopened_opportunities=row["reopened_count"] or 0,
            expired_opportunities=row["expired_count"] or 0,
            removed_opportunities=row["removed_count"] or 0,
            quarantined_opportunities=row["quarantined_count"] or 0,
            free_opportunities=row["free_count"] or 0,
            paid_opportunities=row["paid_count"] or 0,
            freemium_opportunities=row["freemium_count"] or 0,
            unknown_pricing_opportunities=row["unknown_pricing_count"] or 0,
            remote_opportunities=row["remote_count"] or 0,
            stipend_opportunities=row["stipend_count"] or 0,
            certificate_opportunities=row["certificate_count"] or 0,
        )

    # =========================================================================
    # 2. CATEGORY & OPPORTUNITY TYPE DISTRIBUTIONS
    # =========================================================================

    def get_category_distribution(self, limit: int = 15) -> List[CategoryDistributionItemDTO]:
        """Returns distribution by opportunity category with percentages."""
        sql = """
            WITH counts AS (
                SELECT
                    COALESCE(NULLIF(TRIM(category), ''), 'other') as cat,
                    COUNT(*) as total_cnt,
                    COUNT(*) FILTER (WHERE lifecycle_status IN ('active', 'closing_soon') AND quality_status != 'quarantined') as act_cnt
                FROM "Opportunities"
                WHERE quality_status != 'quarantined'
                GROUP BY cat
            ),
            totals AS (
                SELECT SUM(total_cnt) as overall_total FROM counts
            )
            SELECT
                c.cat,
                c.total_cnt,
                c.act_cnt,
                CASE WHEN t.overall_total > 0
                     THEN ROUND((c.total_cnt::numeric / t.overall_total::numeric) * 100.0, 1)
                     ELSE 0.0
                END as pct
            FROM counts c, totals t
            ORDER BY c.total_cnt DESC
            LIMIT %s;
        """
        items: List[CategoryDistributionItemDTO] = []
        with self.db_manager.transaction() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            for r in rows:
                items.append(
                    CategoryDistributionItemDTO(
                        category=r["cat"],
                        count=r["total_cnt"],
                        percentage=float(r["pct"] or 0.0),
                        active_count=r["act_cnt"],
                    )
                )
        return items

    def get_opportunity_type_distribution(self, limit: int = 15) -> List[OpportunityTypeDistributionItemDTO]:
        """Returns distribution by opportunity type with percentages."""
        sql = """
            WITH counts AS (
                SELECT
                    COALESCE(NULLIF(TRIM(opportunity_type), ''), 'other') as opp_type,
                    COUNT(*) as total_cnt,
                    COUNT(*) FILTER (WHERE lifecycle_status IN ('active', 'closing_soon') AND quality_status != 'quarantined') as act_cnt
                FROM "Opportunities"
                WHERE quality_status != 'quarantined'
                GROUP BY opp_type
            ),
            totals AS (
                SELECT SUM(total_cnt) as overall_total FROM counts
            )
            SELECT
                c.opp_type,
                c.total_cnt,
                c.act_cnt,
                CASE WHEN t.overall_total > 0
                     THEN ROUND((c.total_cnt::numeric / t.overall_total::numeric) * 100.0, 1)
                     ELSE 0.0
                END as pct
            FROM counts c, totals t
            ORDER BY c.total_cnt DESC
            LIMIT %s;
        """
        items: List[OpportunityTypeDistributionItemDTO] = []
        with self.db_manager.transaction() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            for r in rows:
                items.append(
                    OpportunityTypeDistributionItemDTO(
                        opportunity_type=r["opp_type"],
                        count=r["total_cnt"],
                        percentage=float(r["pct"] or 0.0),
                        active_count=r["act_cnt"],
                    )
                )
        return items

    # =========================================================================
    # 3. DEADLINE INTELLIGENCE
    # =========================================================================

    def get_deadline_insights(self) -> DeadlineInsightsDTO:
        """
        Returns deadline urgency buckets strictly for active, non-quarantined opportunities.
        """
        sql = """
            SELECT
                COUNT(*) FILTER (WHERE deadline = CURRENT_DATE) as due_today,
                COUNT(*) FILTER (WHERE deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '1 day') as due_24h,
                COUNT(*) FILTER (WHERE deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '3 days') as due_3d,
                COUNT(*) FILTER (WHERE deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '7 days') as due_7d,
                COUNT(*) FILTER (WHERE deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '30 days') as due_30d,
                COUNT(*) FILTER (WHERE deadline IS NOT NULL AND deadline >= CURRENT_DATE) as total_with_deadlines,
                COUNT(*) FILTER (WHERE deadline IS NULL) as total_without_deadlines
            FROM "Opportunities"
            WHERE lifecycle_status IN ('active', 'closing_soon')
              AND quality_status != 'quarantined';
        """
        with self.db_manager.transaction() as cur:
            cur.execute(sql)
            row = cur.fetchone()

        if not row:
            return DeadlineInsightsDTO()

        return DeadlineInsightsDTO(
            due_today=row["due_today"] or 0,
            due_within_24h=row["due_24h"] or 0,
            due_within_3d=row["due_3d"] or 0,
            due_within_7d=row["due_7d"] or 0,
            due_within_30d=row["due_30d"] or 0,
            total_with_deadlines=row["total_with_deadlines"] or 0,
            total_without_deadlines=row["total_without_deadlines"] or 0,
        )

    # =========================================================================
    # 4. ECONOMIC INSIGHTS
    # =========================================================================

    def get_economic_insights(self) -> EconomicInsightsDTO:
        """Aggregates financial, stipend, and certification metrics."""
        sql_counts = """
            SELECT
                COUNT(*) FILTER (WHERE is_free IS TRUE OR LOWER(pricing_type) = 'free') as free_count,
                COUNT(*) FILTER (WHERE paid IS TRUE OR LOWER(pricing_type) = 'paid') as paid_count,
                COUNT(*) FILTER (WHERE LOWER(pricing_type) = 'freemium') as freemium_count,
                COUNT(*) FILTER (WHERE (is_free IS NULL OR is_free IS FALSE) AND (paid IS NULL OR paid IS FALSE) AND (pricing_type IS NULL OR LOWER(pricing_type) IN ('unknown', ''))) as unknown_count,
                COUNT(*) FILTER (WHERE LOWER(stipend_type) NOT IN ('none', '', 'unpaid') AND stipend_type IS NOT NULL) as stipend_count,
                COUNT(*) FILTER (WHERE certificate IS TRUE OR LOWER(certificate_available) = 'yes') as cert_count,
                COUNT(*) FILTER (WHERE application_fee > 0) as fee_count,
                AVG(stipend_amount) FILTER (WHERE stipend_amount > 0) as avg_stipend
            FROM "Opportunities"
            WHERE quality_status != 'quarantined';
        """

        sql_currencies = """
            SELECT
                COALESCE(NULLIF(UPPER(TRIM(stipend_currency)), ''), 'USD') as currency,
                COUNT(*) as cnt
            FROM "Opportunities"
            WHERE LOWER(stipend_type) NOT IN ('none', '', 'unpaid')
              AND stipend_type IS NOT NULL
              AND quality_status != 'quarantined'
            GROUP BY 1
            ORDER BY cnt DESC;
        """

        with self.db_manager.transaction() as cur:
            cur.execute(sql_counts)
            row = cur.fetchone()

            cur.execute(sql_currencies)
            curr_rows = cur.fetchall()

        curr_breakdown = {r["currency"]: r["cnt"] for r in curr_rows} if curr_rows else {}
        avg_stip = round(float(row["avg_stipend"]), 2) if row and row["avg_stipend"] else None

        return EconomicInsightsDTO(
            free_count=row["free_count"] if row else 0,
            paid_count=row["paid_count"] if row else 0,
            freemium_count=row["freemium_count"] if row else 0,
            unknown_count=row["unknown_count"] if row else 0,
            stipend_available_count=row["stipend_count"] if row else 0,
            certificate_available_count=row["cert_count"] if row else 0,
            with_application_fee_count=row["fee_count"] if row else 0,
            average_stipend=avg_stip,
            stipend_currency_breakdown=curr_breakdown,
        )

    # =========================================================================
    # 5. FRESHNESS HEALTH INSIGHTS
    # =========================================================================

    def get_freshness_insights(self) -> FreshnessInsightsDTO:
        """Calculates freshness distribution using Phase 6 temporal boundaries."""
        sql = """
            SELECT
                COUNT(*) FILTER (WHERE COALESCE(last_harvested_at, first_seen_at) >= NOW() - INTERVAL '3 days') as fresh_cnt,
                COUNT(*) FILTER (WHERE COALESCE(last_harvested_at, first_seen_at) < NOW() - INTERVAL '3 days' AND COALESCE(last_harvested_at, first_seen_at) >= NOW() - INTERVAL '7 days') as aging_cnt,
                COUNT(*) FILTER (WHERE COALESCE(last_harvested_at, first_seen_at) < NOW() - INTERVAL '7 days' AND COALESCE(last_harvested_at, first_seen_at) >= NOW() - INTERVAL '30 days') as stale_cnt,
                COUNT(*) FILTER (WHERE COALESCE(last_harvested_at, first_seen_at) < NOW() - INTERVAL '30 days') as severely_stale_cnt
            FROM "Opportunities"
            WHERE quality_status != 'quarantined'
              AND lifecycle_status NOT IN ('removed', 'expired', 'closed');
        """
        with self.db_manager.transaction() as cur:
            cur.execute(sql)
            row = cur.fetchone()

        if not row:
            return FreshnessInsightsDTO()

        return FreshnessInsightsDTO(
            fresh_count=row["fresh_cnt"] or 0,
            aging_count=row["aging_cnt"] or 0,
            stale_count=row["stale_cnt"] or 0,
            severely_stale_count=row["severely_stale_cnt"] or 0,
        )

    # =========================================================================
    # 6. OPPORTUNITY TRENDS & VELOCITY
    # =========================================================================

    def get_discovery_trends(self, days: int = 30) -> TrendSummaryDTO:
        """
        Computes discovery velocity over time using first_seen_at.
        Compares current period [NOW() - days, NOW()] against previous period
        [NOW() - 2*days, NOW() - days].
        """
        days = max(1, min(days, 365))

        # Current vs Previous Period Count
        sql_periods = """
            SELECT
                COUNT(*) FILTER (WHERE first_seen_at >= NOW() - (%s * INTERVAL '1 day')) as curr_count,
                COUNT(*) FILTER (WHERE first_seen_at >= NOW() - ((2 * %s) * INTERVAL '1 day') AND first_seen_at < NOW() - (%s * INTERVAL '1 day')) as prev_count
            FROM "Opportunities"
            WHERE quality_status != 'quarantined';
        """

        # Daily Trend Series
        sql_series = """
            SELECT
                TO_CHAR(DATE_TRUNC('day', first_seen_at), 'YYYY-MM-DD') as day_bucket,
                COUNT(*) as bucket_count
            FROM "Opportunities"
            WHERE first_seen_at >= NOW() - (%s * INTERVAL '1 day')
              AND quality_status != 'quarantined'
            GROUP BY 1
            ORDER BY 1 ASC;
        """

        with self.db_manager.transaction() as cur:
            cur.execute(sql_periods, (days, days, days))
            period_row = cur.fetchone()

            cur.execute(sql_series, (days,))
            series_rows = cur.fetchall()

        curr_count = period_row["curr_count"] if period_row else 0
        prev_count = period_row["prev_count"] if period_row else 0
        abs_change = curr_count - prev_count

        # Division-by-zero safe percentage calculation
        if prev_count == 0:
            pct_change = 100.0 if curr_count > 0 else 0.0
        else:
            pct_change = round(((curr_count - prev_count) / prev_count) * 100.0, 1)

        trend_dir = "up" if abs_change > 0 else ("down" if abs_change < 0 else "flat")

        points = [
            TrendPointDTO(
                period_label=r["day_bucket"],
                date_start=r["day_bucket"],
                count=r["bucket_count"],
            )
            for r in series_rows
        ]

        return TrendSummaryDTO(
            metric_name="opportunity_discovery_velocity",
            current_period_count=curr_count,
            previous_period_count=prev_count,
            absolute_change=abs_change,
            percentage_change=pct_change,
            trend_direction=trend_dir,
            points=points,
        )

    # =========================================================================
    # 7. USER PERSONAL INTELLIGENCE (PRIVATE)
    # =========================================================================

    def get_user_personal_intelligence(self, user_id: Any) -> UserPersonalIntelligenceDTO:
        """
        Retrieves user-private metrics, saved opportunities, search activity, and preferences.
        Guarantees strict tenant isolation by binding user_id to all subqueries.
        """
        if not user_id:
            return UserPersonalIntelligenceDTO(user_id="")
        try:
            import uuid
            uid_str = str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return UserPersonalIntelligenceDTO(user_id="")
        user_id = uid_str

        # 1. Saved Opportunities Analytics
        sql_saved = """
            SELECT
                COUNT(*) as total_saved,
                COUNT(*) FILTER (WHERE o.lifecycle_status IN ('active', 'closing_soon') AND o.quality_status != 'quarantined') as active_saved,
                COUNT(*) FILTER (WHERE o.lifecycle_status = 'closing_soon' AND o.quality_status != 'quarantined') as closing_soon_saved,
                COUNT(*) FILTER (WHERE o.lifecycle_status = 'expired') as expired_saved,
                COUNT(*) FILTER (WHERE o.deadline >= CURRENT_DATE AND o.deadline <= CURRENT_DATE + INTERVAL '7 days' AND o.quality_status != 'quarantined') as deadlines_7d
            FROM "SavedOpportunities" s
            JOIN "Opportunities" o ON s.opportunity_id = o.id
            WHERE s.user_id = %s;
        """

        sql_saved_cats = """
            SELECT
                COALESCE(NULLIF(o.category, ''), 'other') as cat,
                COUNT(*) as count
            FROM "SavedOpportunities" s
            JOIN "Opportunities" o ON s.opportunity_id = o.id
            WHERE s.user_id = %s
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 5;
        """

        sql_saved_types = """
            SELECT
                COALESCE(NULLIF(o.opportunity_type, ''), 'other') as opp_type,
                COUNT(*) as count
            FROM "SavedOpportunities" s
            JOIN "Opportunities" o ON s.opportunity_id = o.id
            WHERE s.user_id = %s
            GROUP BY 1
            ORDER BY count DESC
            LIMIT 5;
        """

        # 2. User Preferences
        sql_prefs = """
            SELECT
                skills,
                preferred_categories,
                preferred_types,
                prefers_remote,
                preferred_location
            FROM "UserPreferences"
            WHERE user_id = %s;
        """

        # 3. User Search History
        sql_recent_searches = """
            SELECT
                query_text,
                searched_at
            FROM "UserSearchHistory"
            WHERE user_id = %s
            ORDER BY searched_at DESC
            LIMIT 5;
        """

        sql_frequent_searches = """
            SELECT
                TRIM(query_text) as term,
                COUNT(*) as frequency
            FROM "UserSearchHistory"
            WHERE user_id = %s
              AND searched_at >= NOW() - INTERVAL '30 days'
            GROUP BY 1
            ORDER BY frequency DESC
            LIMIT 5;
        """

        # 4. User Notification Telemetry
        sql_notifs = """
            SELECT
                COUNT(*) as total_received,
                COUNT(*) FILTER (WHERE is_read IS FALSE) as unread_count,
                COUNT(*) FILTER (WHERE event_type = 'new') as count_new,
                COUNT(*) FILTER (WHERE event_type = 'updated') as count_updated,
                COUNT(*) FILTER (WHERE event_type = 'reopened') as count_reopened
            FROM "NotificationOutbox"
            WHERE user_id = %s;
        """

        with self.db_manager.transaction() as cur:
            # Saved
            cur.execute(sql_saved, (user_id,))
            saved_row = cur.fetchone()

            cur.execute(sql_saved_cats, (user_id,))
            saved_cats = [{"category": r["cat"], "count": r["count"]} for r in cur.fetchall()]

            cur.execute(sql_saved_types, (user_id,))
            saved_types = [{"opportunity_type": r["opp_type"], "count": r["count"]} for r in cur.fetchall()]

            # Prefs
            cur.execute(sql_prefs, (user_id,))
            prefs_row = cur.fetchone()

            # Searches
            cur.execute(sql_recent_searches, (user_id,))
            recent_searches = [
                {"query": r["query_text"], "searched_at": r["searched_at"].isoformat() if r["searched_at"] else ""}
                for r in cur.fetchall()
            ]

            cur.execute(sql_frequent_searches, (user_id,))
            frequent_searches = [{"term": r["term"], "frequency": r["frequency"]} for r in cur.fetchall()]

            # Notifications
            cur.execute(sql_notifs, (user_id,))
            notifs_row = cur.fetchone()

        # Parse preferences safely
        pref_cats: List[str] = []
        pref_types: List[str] = []
        pref_skills: List[str] = []
        prefers_remote = None
        pref_location = None

        if prefs_row:
            try:
                raw_cats = prefs_row["preferred_categories"]
                pref_cats = json.loads(raw_cats) if raw_cats and raw_cats.startswith("[") else ([raw_cats] if raw_cats else [])
            except Exception:
                pref_cats = []

            try:
                raw_types = prefs_row["preferred_types"]
                pref_types = json.loads(raw_types) if raw_types and raw_types.startswith("[") else ([raw_types] if raw_types else [])
            except Exception:
                pref_types = []

            try:
                raw_skills = prefs_row["skills"]
                pref_skills = json.loads(raw_skills) if raw_skills and raw_skills.startswith("[") else ([raw_skills] if raw_skills else [])
            except Exception:
                pref_skills = []

            prefers_remote = prefs_row["prefers_remote"]
            pref_location = prefs_row["preferred_location"]

        notif_breakdown = {
            "new": notifs_row["count_new"] if notifs_row else 0,
            "updated": notifs_row["count_updated"] if notifs_row else 0,
            "reopened": notifs_row["count_reopened"] if notifs_row else 0,
        }

        return UserPersonalIntelligenceDTO(
            user_id=user_id,
            total_saved=saved_row["total_saved"] if saved_row else 0,
            active_saved=saved_row["active_saved"] if saved_row else 0,
            closing_soon_saved=saved_row["closing_soon_saved"] if saved_row else 0,
            expired_saved=saved_row["expired_saved"] if saved_row else 0,
            top_saved_categories=saved_cats,
            top_saved_types=saved_types,
            preferred_categories=pref_cats,
            preferred_types=pref_types,
            prefers_remote=prefers_remote,
            preferred_location=pref_location,
            skills=pref_skills,
            recent_searches=recent_searches,
            frequent_search_terms=frequent_searches,
            notifications_received=notifs_row["total_received"] if notifs_row else 0,
            unread_notifications=notifs_row["unread_count"] if notifs_row else 0,
            notification_breakdown=notif_breakdown,
            saved_deadlines_within_7d=saved_row["deadlines_7d"] if saved_row else 0,
        )

    # =========================================================================
    # 8. ADMIN OPERATIONAL ANALYTICS
    # =========================================================================

    def get_admin_operational_analytics(self) -> AdminAnalyticsOverviewDTO:
        """
        Retrieves comprehensive operational intelligence across sources, quality gates,
        lifecycle statuses, and Phase 7 notification delivery rates.
        """
        overview = self.get_platform_overview()
        trends = self.get_discovery_trends(days=30)

        # 1. Source Health & Telemetry
        sql_sources = """
            SELECT
                source_id,
                health_status,
                items_seen,
                items_created,
                items_updated,
                items_rejected,
                failure_count,
                success_count,
                latency,
                last_success,
                last_failure,
                CASE WHEN items_seen > 0
                     THEN ROUND((items_rejected::numeric / items_seen::numeric) * 100.0, 1)
                     ELSE 0.0
                END as malformed_pct
            FROM "SourceHealth"
            ORDER BY items_seen DESC
            LIMIT 25;
        """

        # 2. Lifecycle Status Breakdown
        sql_lifecycle = """
            SELECT
                lifecycle_status,
                COUNT(*) as count
            FROM "Opportunities"
            GROUP BY lifecycle_status
            ORDER BY count DESC;
        """

        # 3. Quality Status Breakdown
        sql_quality = """
            SELECT
                quality_status,
                COUNT(*) as count
            FROM "Opportunities"
            GROUP BY quality_status
            ORDER BY count DESC;
        """

        # 4. Quarantine Summary
        sql_quarantine = """
            SELECT
                COALESCE(NULLIF(TRIM(quarantine_reason), ''), 'Unspecified') as reason,
                COUNT(*) as count
            FROM "Opportunities"
            WHERE quality_status = 'quarantined'
            GROUP BY 1
            ORDER BY count DESC;
        """

        # 5. Phase 7 Notification Metrics
        sql_notifs = """
            SELECT
                COUNT(*) as total_outbox,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'sent') as sent_count,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                SUM(attempt_count) as total_attempts
            FROM "NotificationOutbox";
        """

        with self.db_manager.transaction() as cur:
            cur.execute(sql_sources)
            source_rows = cur.fetchall()

            cur.execute(sql_lifecycle)
            lifecycle_rows = cur.fetchall()

            cur.execute(sql_quality)
            quality_rows = cur.fetchall()

            cur.execute(sql_quarantine)
            quarantine_rows = cur.fetchall()

            cur.execute(sql_notifs)
            notif_row = cur.fetchone()

        sources = [
            SourceAnalyticsDTO(
                source_id=r["source_id"],
                health_status=r["health_status"] or "UNKNOWN",
                items_seen=r["items_seen"] or 0,
                items_created=r["items_created"] or 0,
                items_updated=r["items_updated"] or 0,
                items_rejected=r["items_rejected"] or 0,
                failure_count=r["failure_count"] or 0,
                success_count=r["success_count"] or 0,
                malformed_rate=float(r["malformed_pct"] or 0.0),
                latency=float(r["latency"] or 0.0),
                last_success=r["last_success"].isoformat() if r["last_success"] else None,
                last_failure=r["last_failure"].isoformat() if r["last_failure"] else None,
            )
            for r in source_rows
        ]

        lifecycle_dist = {r["lifecycle_status"]: r["count"] for r in lifecycle_rows}
        quality_dist = {r["quality_status"]: r["count"] for r in quality_rows}
        quarantine_reasons = {r["reason"]: r["count"] for r in quarantine_rows}

        total_notifs = notif_row["total_outbox"] if notif_row else 0
        sent_notifs = notif_row["sent_count"] if notif_row else 0
        failed_notifs = notif_row["failed_count"] if notif_row else 0
        pending_notifs = notif_row["pending_count"] if notif_row else 0
        total_att = notif_row["total_attempts"] if notif_row and notif_row["total_attempts"] else 0

        # Zero-attempt safe delivery rate
        attempted = sent_notifs + failed_notifs
        delivery_rate = round((sent_notifs / attempted) * 100.0, 1) if attempted > 0 else 100.0

        notif_metrics = {
            "total_records": total_notifs,
            "pending": pending_notifs,
            "sent": sent_notifs,
            "failed": failed_notifs,
            "total_attempts": total_att,
            "delivery_success_rate": delivery_rate,
        }

        quarantine_summary = {
            "total_quarantined": overview.quarantined_opportunities,
            "reasons_breakdown": quarantine_reasons,
        }

        return AdminAnalyticsOverviewDTO(
            platform_overview=overview,
            source_health_summary=sources,
            lifecycle_distribution=lifecycle_dist,
            quality_distribution=quality_dist,
            quarantine_summary=quarantine_summary,
            notification_metrics=notif_metrics,
            recent_trends=trends,
        )
