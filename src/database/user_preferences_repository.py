"""
User Preferences and Search History Repository for CyberScout AI.

Handles persistence, retrieval, and behavioral profiling for Phase 5 Personalization
with strict RLS compatibility and SQL injection protection.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.base_repository import row_to_dict
from src.core.exceptions import RepositoryError
from src.models.recommendation_models import UserPreferencesDTO

logger = get_logger(__name__)


class UserPreferencesRepository:
    """Repository for managing user career preferences and search history."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def _normalize_uid(self, user_id: Any) -> Optional[str]:
        """Safely parses and validates user_id as canonical UUID string."""
        if user_id is None:
            return None
        try:
            import uuid
            return str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Invalid non-UUID user_id: {user_id}")
            return None

    @staticmethod
    def _parse_json_list(value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    @classmethod
    def _preferences_from_row(cls, data: Dict[str, Any]) -> UserPreferencesDTO:
        return UserPreferencesDTO(
            skills=cls._parse_json_list(data.get("skills")),
            interests=cls._parse_json_list(data.get("interests")),
            preferred_categories=cls._parse_json_list(data.get("preferred_categories")),
            preferred_types=cls._parse_json_list(data.get("preferred_types")),
            prefers_remote=data.get("prefers_remote"),
            preferred_location=data.get("preferred_location"),
            experience_level=data.get("experience_level"),
            email_notifications_enabled=bool(data.get("email_notifications_enabled", True)),
            in_app_notifications_enabled=bool(data.get("in_app_notifications_enabled", True)),
            notify_new_opportunities=bool(data.get("notify_new_opportunities", True)),
            notify_meaningful_updates=bool(data.get("notify_meaningful_updates", True)),
            notify_reopened_opportunities=bool(data.get("notify_reopened_opportunities", True)),
            delivery_mode=str(data.get("delivery_mode", "digest")),
            digest_frequency=str(data.get("digest_frequency", "daily")),
            quiet_hours_enabled=bool(data.get("quiet_hours_enabled", False)),
            quiet_hours_start=str(data.get("quiet_hours_start", "22:00")),
            quiet_hours_end=str(data.get("quiet_hours_end", "08:00")),
            timezone=str(data.get("timezone", "UTC")),
            min_score_threshold=float(data.get("min_score_threshold", 0.0) or 0.0),
        )

    @staticmethod
    def _behavior_from_rows(rows: List[Any]) -> Tuple[List[str], List[str]]:
        tags_set: Set[str] = set()
        categories_set: Set[str] = set()

        for row in rows:
            if hasattr(row, "get"):
                raw_tags = row.get("tags")
                category = row.get("category")
                opportunity_type = row.get("opportunity_type")
            else:
                raw_tags, category, opportunity_type = row[0], row[1], row[2]

            if category and str(category).strip():
                categories_set.add(str(category).strip().lower())
            if opportunity_type and str(opportunity_type).strip():
                categories_set.add(str(opportunity_type).strip().lower())

            if isinstance(raw_tags, list):
                tags_set.update(
                    str(tag).strip().lower()
                    for tag in raw_tags
                    if tag and str(tag).strip()
                )
            elif isinstance(raw_tags, str) and raw_tags:
                try:
                    parsed_tags = json.loads(raw_tags)
                except json.JSONDecodeError:
                    parsed_tags = raw_tags.split(",")
                if isinstance(parsed_tags, list):
                    tags_set.update(
                        str(tag).strip().lower()
                        for tag in parsed_tags
                        if tag and str(tag).strip()
                    )
                else:
                    tags_set.update(
                        tag.strip().lower()
                        for tag in raw_tags.split(",")
                        if tag.strip()
                    )

        return sorted(tags_set), sorted(categories_set)

    def get_preferences(self, user_id: Any) -> Optional[UserPreferencesDTO]:
        """
        Retrieves declared career preferences for a user.

        Args:
            user_id: User identifier.

        Returns:
            UserPreferencesDTO if record exists, else None.
        """
        uid = self._normalize_uid(user_id)
        if uid is None:
            return None

        sql = """
            SELECT skills, interests, preferred_categories, preferred_types,
                   prefers_remote, preferred_location, experience_level,
                   email_notifications_enabled, in_app_notifications_enabled,
                   notify_new_opportunities, notify_meaningful_updates,
                   notify_reopened_opportunities, delivery_mode, digest_frequency,
                   quiet_hours_enabled, quiet_hours_start, quiet_hours_end,
                   timezone, min_score_threshold
            FROM "UserPreferences"
            WHERE user_id = %s;
        """
        try:
            with self.db_manager.user_context(uid) as cursor:
                cursor.execute(sql, (uid,))
                row = cursor.fetchone()

            if not row:
                return None

            d = row_to_dict(row)
            return self._preferences_from_row(d)
        except Exception as e:
            logger.error(f"Failed to get preferences for user {user_id}: {e}")
            raise RepositoryError(f"Failed to get user preferences: {e}", original_exception=e)

    def get_personalization_data(
        self, user_id: Any
    ) -> Tuple[Optional[UserPreferencesDTO], Tuple[List[str], List[str]]]:
        """Loads declared preferences and saved-item behavior using one database query."""
        uid = self._normalize_uid(user_id)
        if uid is None:
            return None, ([], [])

        sql = """
            SELECT
                p.user_id AS preference_user_id,
                p.skills,
                p.interests,
                p.preferred_categories,
                p.preferred_types,
                p.prefers_remote,
                p.preferred_location,
                p.experience_level,
                p.email_notifications_enabled,
                p.in_app_notifications_enabled,
                p.notify_new_opportunities,
                p.notify_meaningful_updates,
                p.notify_reopened_opportunities,
                p.delivery_mode,
                p.digest_frequency,
                p.quiet_hours_enabled,
                p.quiet_hours_start,
                p.quiet_hours_end,
                p.timezone,
                p.min_score_threshold,
                COALESCE((
                    SELECT json_agg(json_build_object(
                        'tags', saved.tags,
                        'category', saved.category,
                        'opportunity_type', saved.opportunity_type
                    ))
                    FROM (
                        SELECT o.tags, o.category, o.opportunity_type
                        FROM "SavedOpportunities" so
                        JOIN "Opportunities" o ON o.id = so.opportunity_id
                        WHERE so.user_id = %s
                        LIMIT 50
                    ) saved
                ), '[]'::json) AS saved_behavior
            FROM (SELECT 1) AS request_context
            LEFT JOIN "UserPreferences" p ON p.user_id = %s;
        """
        try:
            with self.db_manager.user_context(uid) as cursor:
                cursor.execute(sql, (uid, uid))
                row = cursor.fetchone()
            if not row:
                return None, ([], [])

            data = row_to_dict(row, cursor.description)
            preferences = (
                self._preferences_from_row(data)
                if data.get("preference_user_id") is not None
                else None
            )
            saved_behavior = data.get("saved_behavior") or []
            if isinstance(saved_behavior, str):
                saved_behavior = json.loads(saved_behavior)
            if not isinstance(saved_behavior, list):
                saved_behavior = []

            return preferences, self._behavior_from_rows(saved_behavior)
        except Exception as e:
            logger.error(f"Failed to load personalization data for user {user_id}: {e}")
            raise RepositoryError(f"Failed to load user personalization data: {e}", original_exception=e)

    def save_preferences(self, user_id: Any, preferences: UserPreferencesDTO) -> bool:
        """
        Upserts preferences for a user including Phase 7 notification settings.

        Args:
            user_id: User identifier.
            preferences: UserPreferencesDTO to persist.

        Returns:
            True on successful save.
        """
        uid = self._normalize_uid(user_id)
        if uid is None:
            return False

        skills_json = json.dumps(preferences.skills)
        interests_json = json.dumps(preferences.interests)
        categories_json = json.dumps(preferences.preferred_categories)
        types_json = json.dumps(preferences.preferred_types)
        pref_id = f"pref_{uid}"

        sql = """
            INSERT INTO "UserPreferences" (
                id, user_id, skills, interests, preferred_categories, preferred_types,
                prefers_remote, preferred_location, experience_level,
                email_notifications_enabled, in_app_notifications_enabled,
                notify_new_opportunities, notify_meaningful_updates,
                notify_reopened_opportunities, delivery_mode, digest_frequency,
                quiet_hours_enabled, quiet_hours_start, quiet_hours_end,
                timezone, min_score_threshold, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (user_id) DO UPDATE SET
                skills = EXCLUDED.skills,
                interests = EXCLUDED.interests,
                preferred_categories = EXCLUDED.preferred_categories,
                preferred_types = EXCLUDED.preferred_types,
                prefers_remote = EXCLUDED.prefers_remote,
                preferred_location = EXCLUDED.preferred_location,
                experience_level = EXCLUDED.experience_level,
                email_notifications_enabled = EXCLUDED.email_notifications_enabled,
                in_app_notifications_enabled = EXCLUDED.in_app_notifications_enabled,
                notify_new_opportunities = EXCLUDED.notify_new_opportunities,
                notify_meaningful_updates = EXCLUDED.notify_meaningful_updates,
                notify_reopened_opportunities = EXCLUDED.notify_reopened_opportunities,
                delivery_mode = EXCLUDED.delivery_mode,
                digest_frequency = EXCLUDED.digest_frequency,
                quiet_hours_enabled = EXCLUDED.quiet_hours_enabled,
                quiet_hours_start = EXCLUDED.quiet_hours_start,
                quiet_hours_end = EXCLUDED.quiet_hours_end,
                timezone = EXCLUDED.timezone,
                min_score_threshold = EXCLUDED.min_score_threshold,
                updated_at = CURRENT_TIMESTAMP;
        """
        try:
            with self.db_manager.user_context(uid) as cursor:
                cursor.execute(
                    sql,
                    (
                        pref_id,
                        uid,
                        skills_json,
                        interests_json,
                        categories_json,
                        types_json,
                        preferences.prefers_remote,
                        preferences.preferred_location,
                        preferences.experience_level,
                        preferences.email_notifications_enabled,
                        preferences.in_app_notifications_enabled,
                        preferences.notify_new_opportunities,
                        preferences.notify_meaningful_updates,
                        preferences.notify_reopened_opportunities,
                        preferences.delivery_mode,
                        preferences.digest_frequency,
                        preferences.quiet_hours_enabled,
                        preferences.quiet_hours_start,
                        preferences.quiet_hours_end,
                        preferences.timezone,
                        preferences.min_score_threshold,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save preferences for user {user_id}: {e}")
            raise RepositoryError(f"Failed to save user preferences: {e}", original_exception=e)

    def get_all_subscribed_users(self, target_user_ids: Optional[List[int]] = None) -> List[Tuple[int, str, UserPreferencesDTO]]:
        """
        Retrieves all active users with their preferences for notification matching.
        Users without saved preferences receive default preferences.
        """
        sql = """
        SELECT u.id, u.email,
               p.skills, p.interests, p.preferred_categories, p.preferred_types,
               p.prefers_remote, p.preferred_location, p.experience_level,
               p.email_notifications_enabled, p.in_app_notifications_enabled,
               p.notify_new_opportunities, p.notify_meaningful_updates,
               p.notify_reopened_opportunities, p.delivery_mode, p.digest_frequency,
               p.quiet_hours_enabled, p.quiet_hours_start, p.quiet_hours_end,
               p.timezone, p.min_score_threshold
        FROM "Users" u
        LEFT JOIN "UserPreferences" p ON p.user_id = u.id
        WHERE u.is_active != 0
        """
        params: List[Any] = []
        if target_user_ids:
            placeholders = ", ".join(["%s"] * len(target_user_ids))
            sql += f" AND u.id IN ({placeholders})"
            params.extend([self._normalize_uid(x) for x in target_user_ids])
        sql += ";"
        try:
            with self.db_manager.service_context() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                subscribed = []
                for r in rows:
                    d = row_to_dict(r)
                    uid = int(d["id"])
                    email = str(d["email"])

                    def parse_json_list(val: Any) -> List[str]:
                        if not val:
                            return []
                        if isinstance(val, list):
                            return val
                        try:
                            res = json.loads(val)
                            return res if isinstance(res, list) else []
                        except Exception:
                            return []

                    # If no preferences row, defaults apply
                    if d.get("email_notifications_enabled") is None and d.get("skills") is None:
                        prefs = UserPreferencesDTO()
                    else:
                        prefs = UserPreferencesDTO(
                            skills=parse_json_list(d.get("skills")),
                            interests=parse_json_list(d.get("interests")),
                            preferred_categories=parse_json_list(d.get("preferred_categories")),
                            preferred_types=parse_json_list(d.get("preferred_types")),
                            prefers_remote=d.get("prefers_remote"),
                            preferred_location=d.get("preferred_location"),
                            experience_level=d.get("experience_level"),
                            email_notifications_enabled=bool(d.get("email_notifications_enabled", True)),
                            in_app_notifications_enabled=bool(d.get("in_app_notifications_enabled", True)),
                            notify_new_opportunities=bool(d.get("notify_new_opportunities", True)),
                            notify_meaningful_updates=bool(d.get("notify_meaningful_updates", True)),
                            notify_reopened_opportunities=bool(d.get("notify_reopened_opportunities", True)),
                            delivery_mode=str(d.get("delivery_mode", "digest")),
                            digest_frequency=str(d.get("digest_frequency", "daily")),
                            quiet_hours_enabled=bool(d.get("quiet_hours_enabled", False)),
                            quiet_hours_start=str(d.get("quiet_hours_start", "22:00")),
                            quiet_hours_end=str(d.get("quiet_hours_end", "08:00")),
                            timezone=str(d.get("timezone", "UTC")),
                            min_score_threshold=float(d.get("min_score_threshold", 0.0) or 0.0),
                        )

                    if prefs.email_notifications_enabled or prefs.in_app_notifications_enabled:
                        subscribed.append((uid, email, prefs))
                return subscribed
        except Exception as e:
            logger.error(f"Failed to fetch subscribed users: {e}")
            return []

    def record_search(
        self,
        user_id: Any,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Records a user discovery search action for behavioral relevance without spamming.
        """
        uid = self._normalize_uid(user_id)
        clean_q = (query_text or "").strip()
        if uid is None or not clean_q:
            return False

        filters_json = json.dumps(filters or {})
        rec_id = f"ush_{uuid4().hex[:16]}"

        sql = """
            INSERT INTO "UserSearchHistory" (id, user_id, query_text, filters_json, searched_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP);
        """
        try:
            with self.db_manager.user_context(uid) as cursor:
                cursor.execute(sql, (rec_id, uid, clean_q[:255], filters_json))
            return True
        except Exception as e:
            logger.warning(f"Failed to record search for user {user_id}: {e}")
            return False

    def get_recent_searches(self, user_id: Any, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves recent searches performed by the user."""
        uid = self._normalize_uid(user_id)
        if uid is None:
            return []

        sql = """
            SELECT query_text, filters_json, searched_at
            FROM "UserSearchHistory"
            WHERE user_id = %s
            ORDER BY searched_at DESC
            LIMIT %s;
        """
        try:
            with self.db_manager.user_context(uid) as cursor:
                cursor.execute(sql, (uid, max(1, min(limit, 20))))
                rows = cursor.fetchall()

            results = []
            for row in rows:
                if hasattr(row, "get"):
                    q = row.get("query_text")
                    f = row.get("filters_json")
                    t = row.get("searched_at")
                else:
                    q = row[0]
                    f = row[1]
                    t = row[2]
                results.append({
                    "query_text": q,
                    "filters": json.loads(f) if f and isinstance(f, str) else (f or {}),
                    "searched_at": t,
                })
            return results
        except Exception as e:
            logger.warning(f"Failed to get recent searches for user {user_id}: {e}")
            return []

    def get_user_behavior_profile(self, user_id: Any) -> Tuple[List[str], List[str]]:
        """
        Derives behavioral signals from the user's saved opportunities.

        Returns:
            Tuple of (aggregated_tags, aggregated_categories).
        """
        uid = self._normalize_uid(user_id)
        if uid is None:
            return [], []

        sql = """
            SELECT o.tags, o.category, o.opportunity_type
            FROM "SavedOpportunities" so
            JOIN "Opportunities" o ON o.id = so.opportunity_id
            WHERE so.user_id = %s
            LIMIT 50;
        """
        try:
            with self.db_manager.user_context(uid) as cursor:
                cursor.execute(sql, (uid,))
                rows = cursor.fetchall()
            return self._behavior_from_rows(rows)
        except Exception as e:
            logger.warning(f"Failed to compute behavior profile for user {user_id}: {e}")
            return [], []
