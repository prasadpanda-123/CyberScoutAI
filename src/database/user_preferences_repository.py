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
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (uid,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            d = row_to_dict(row)

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

            return UserPreferencesDTO(
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
        except Exception as e:
            logger.error(f"Failed to get preferences for user {user_id}: {e}")
            raise RepositoryError(f"Failed to get user preferences: {e}", original_exception=e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
            with self.db_manager.transaction() as cursor:
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
            with self.db_manager.transaction() as cursor:
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
            with self.db_manager.transaction() as cursor:
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
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (uid, max(1, min(limit, 20))))
            rows = cursor.fetchall()
            cursor.close()

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
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (uid,))
            rows = cursor.fetchall()
            cursor.close()

            tags_set: Set[str] = set()
            cats_set: Set[str] = set()

            for row in rows:
                if hasattr(row, "get"):
                    raw_tags = row.get("tags")
                    cat = row.get("category")
                    op_type = row.get("opportunity_type")
                else:
                    raw_tags = row[0]
                    cat = row[1]
                    op_type = row[2]

                if cat and str(cat).strip():
                    cats_set.add(str(cat).strip().lower())
                if op_type and str(op_type).strip():
                    cats_set.add(str(op_type).strip().lower())

                if raw_tags:
                    if isinstance(raw_tags, list):
                        for t in raw_tags:
                            if t and str(t).strip():
                                tags_set.add(str(t).strip().lower())
                    elif isinstance(raw_tags, str):
                        try:
                            parsed = json.loads(raw_tags)
                            if isinstance(parsed, list):
                                for t in parsed:
                                    if t and str(t).strip():
                                        tags_set.add(str(t).strip().lower())
                            else:
                                for t in raw_tags.split(","):
                                    if t.strip():
                                        tags_set.add(t.strip().lower())
                        except Exception:
                            for t in raw_tags.split(","):
                                if t.strip():
                                    tags_set.add(t.strip().lower())

            return sorted(list(tags_set)), sorted(list(cats_set))
        except Exception as e:
            logger.warning(f"Failed to compute behavior profile for user {user_id}: {e}")
            return [], []
        finally:
            try:
                conn.close()
            except Exception:
                pass
