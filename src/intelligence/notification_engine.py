"""
Notification Engine for CyberScout AI (Phase 7).

Orchestrates event classification, user preference matching, quality/lifecycle
filtering, deterministic deduplication key generation, and outbox persistence.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.notification_repository import NotificationRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.intelligence.eligibility_checker import EligibilityChecker
from src.intelligence.meaningful_change_evaluator import MeaningfulChangeEvaluator
from src.models.enums import (
    ChangeClassification,
    NotificationChannel,
    NotificationDeliveryMode,
    NotificationEventType,
    NotificationStatus,
)
from src.models.notification_models import NotificationOutboxDTO
from src.models.opportunity import Opportunity
from src.models.recommendation_models import UserPreferencesDTO
from src.services.ranking_service import RankingService

logger = get_logger(__name__)


class NotificationEngine:
    """
    Core event-driven notification engine that gates, personalizes,
    and deduplicates notifications into PostgreSQL NotificationOutbox.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        notification_repo: Optional[NotificationRepository] = None,
        preferences_repo: Optional[UserPreferencesRepository] = None,
        ranking_service: Optional[RankingService] = None,
        eligibility_checker: Optional[EligibilityChecker] = None,
        target_user_ids: Optional[List[int]] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.notification_repo = notification_repo or NotificationRepository(db_manager=self.db_manager)
        self.preferences_repo = preferences_repo or UserPreferencesRepository(db_manager=self.db_manager)
        self.ranking_service = ranking_service or RankingService()
        self.eligibility_checker = eligibility_checker or EligibilityChecker()
        self.target_user_ids = target_user_ids

    def is_opportunity_eligible_for_notification(self, opp: Opportunity) -> bool:
        """
        Enforces Phase 6 quality and lifecycle safety gates:
        QUARANTINED, SEVERELY_STALE, REMOVED, or EXPIRED opportunities
        must NEVER trigger normal user notifications.
        """
        # 1. Quality status check
        val_q = getattr(opp, "quality_status", "")
        if hasattr(val_q, "value"):
            val_q = val_q.value
        q_status = str(val_q or "").lower()
        if any(s in q_status for s in ("quarantine", "stale", "reject", "fail", "unverified")):
            return False

        # 2. Rejection & spam check
        if getattr(opp, "is_rejected", False):
            return False
        if getattr(opp, "spam_score", 0.0) > 0.0:
            return False

        # 3. Lifecycle status check
        val_l = getattr(opp, "lifecycle_status", "")
        if hasattr(val_l, "value"):
            val_l = val_l.value
        l_status = str(val_l or "").lower()
        if any(s in l_status for s in ("quarantine", "removed", "closed", "expired")):
            return False

        # 4. Status check
        val_s = getattr(opp, "status", "")
        if hasattr(val_s, "value"):
            val_s = val_s.value
        status = str(val_s or "").lower()
        if any(s in status for s in ("expired", "archived", "closed")):
            return False

        return True

    def process_harvest_events(
        self,
        new_items: Optional[List[Opportunity]] = None,
        updated_items: Optional[List[Tuple[Opportunity, Opportunity]]] = None,
        reopened_items: Optional[List[Opportunity]] = None,
        target_user_ids: Optional[List[int]] = None,
    ) -> int:
        """
        Processes harvested opportunity events and persists eligible notifications into outbox.

        Args:
            new_items: Newly created opportunities.
            updated_items: Tuples of (candidate_opp, existing_opp).
            reopened_items: Previously inactive opportunities that became actionable.
            target_user_ids: Optional list of user IDs to scope notification processing.

        Returns:
            Count of queued notifications.
        """
        metrics = {"queued": 0, "skipped": 0, "duplicates": 0}

        # 1. Fetch subscribed users
        uids = target_user_ids or self.target_user_ids
        try:
            subscribers = self.preferences_repo.get_all_subscribed_users(target_user_ids=uids)
        except Exception as e:
            logger.error(f"Failed to fetch subscribed users for notification engine: {e}")
            return metrics["queued"]

        if not subscribers:
            logger.info("No subscribed users found for notifications.")
            return metrics["queued"]

        outbox_records: List[NotificationOutboxDTO] = []

        # 2. Process NEW items
        for opp in (new_items or []):
            if not self.is_opportunity_eligible_for_notification(opp):
                metrics["skipped"] += 1
                continue

            fp = MeaningfulChangeEvaluator.compute_fingerprint(opp)
            for uid, email, prefs in subscribers:
                if not prefs.notify_new_opportunities:
                    continue
                if not self._check_user_match(opp, prefs):
                    continue

                dedup_key = f"user:{uid}:opp:{opp.id}:event:new"
                outbox_records.append(
                    NotificationOutboxDTO(
                        user_id=uid,
                        opportunity_id=opp.id,
                        event_type=NotificationEventType.NEW.value,
                        deduplication_key=dedup_key,
                        delivery_mode=prefs.delivery_mode,
                        change_fingerprint=fp,
                        status=NotificationStatus.PENDING.value,
                        metadata_json={"match_reasons": self._get_match_reasons(opp, prefs)},
                    )
                )

        # 3. Process UPDATED items
        for item in (updated_items or []):
            candidate, existing = item if isinstance(item, (tuple, list)) else (item, None)
            if not self.is_opportunity_eligible_for_notification(candidate):
                metrics["skipped"] += 1
                continue

            change_dto = MeaningfulChangeEvaluator.evaluate(candidate, existing)
            if not change_dto.is_meaningful:
                metrics["skipped"] += 1
                continue

            fp = change_dto.change_fingerprint
            for uid, email, prefs in subscribers:
                if not prefs.notify_meaningful_updates:
                    continue
                if not self._check_user_match(candidate, prefs):
                    continue

                dedup_key = f"user:{uid}:opp:{candidate.id}:event:updated:{fp}"
                outbox_records.append(
                    NotificationOutboxDTO(
                        user_id=uid,
                        opportunity_id=candidate.id,
                        event_type=NotificationEventType.UPDATED.value,
                        deduplication_key=dedup_key,
                        delivery_mode=prefs.delivery_mode,
                        change_fingerprint=fp,
                        status=NotificationStatus.PENDING.value,
                        metadata_json={
                            "changed_fields": change_dto.changed_fields,
                            "match_reasons": self._get_match_reasons(candidate, prefs),
                        },
                    )
                )

        # 4. Process REOPENED items
        for opp in (reopened_items or []):
            if not self.is_opportunity_eligible_for_notification(opp):
                metrics["skipped"] += 1
                continue

            fp = MeaningfulChangeEvaluator.compute_fingerprint(opp)
            for uid, email, prefs in subscribers:
                if not prefs.notify_reopened_opportunities:
                    continue
                if not self._check_user_match(opp, prefs):
                    continue

                dedup_key = f"user:{uid}:opp:{opp.id}:event:reopened:{fp}"
                outbox_records.append(
                    NotificationOutboxDTO(
                        user_id=uid,
                        opportunity_id=opp.id,
                        event_type=NotificationEventType.REOPENED.value,
                        deduplication_key=dedup_key,
                        delivery_mode=prefs.delivery_mode,
                        change_fingerprint=fp,
                        status=NotificationStatus.PENDING.value,
                        metadata_json={"match_reasons": self._get_match_reasons(opp, prefs)},
                    )
                )

        # 5. Persist into outbox with database-level deduplication
        if outbox_records:
            try:
                inserted = self.notification_repo.enqueue_notifications_batch(outbox_records)
                metrics["queued"] = inserted
                metrics["duplicates"] = len(outbox_records) - inserted
                logger.info(f"Notification engine: {inserted} queued, {metrics['duplicates']} duplicate events resolved.")
            except Exception as e:
                logger.error(f"Failed to persist notifications into outbox: {e}")

        return metrics["queued"]

    def _check_user_match(self, opp: Opportunity, prefs: UserPreferencesDTO) -> bool:
        """Evaluates whether an opportunity matches the user's career preferences."""
        # 1. Eligibility check
        eligibility = self.eligibility_checker.check_eligibility(opp, prefs)
        if eligibility.is_ineligible:
            return False

        # If user has no specific preferences set, broad eligibility passes
        if prefs.is_empty:
            return True

        # 2. Remote check
        if prefs.prefers_remote is True and not opp.remote:
            return False

        # 3. Category match
        if prefs.preferred_categories:
            opp_cat = str(opp.category or "").lower().strip()
            if opp_cat not in prefs.preferred_categories and opp_cat != "other":
                # Allow if matched on skills
                opp_tags = [str(t).lower() for t in (opp.tags or [])]
                has_skill_match = any(s in opp_tags for s in prefs.skills)
                if not has_skill_match:
                    return False

        # 4. Experience level check
        if prefs.experience_level == "beginner":
            if getattr(opp, "difficulty", "unknown").lower() in ("advanced", "expert"):
                return False

        return True

    def _get_match_reasons(self, opp: Opportunity, prefs: UserPreferencesDTO) -> List[str]:
        """Generates concise explanation reasons for why this opportunity matched."""
        reasons: List[str] = []
        if opp.remote and prefs.prefers_remote:
            reasons.append("Remote friendly")
        if opp.is_free or (opp.price_amount is not None and opp.price_amount == 0):
            reasons.append("100% Free")
        if opp.stipend_amount and opp.stipend_amount > 0:
            reasons.append("Includes stipend")
        if opp.category and prefs.preferred_categories and opp.category.lower() in prefs.preferred_categories:
            reasons.append(f"In your category: {opp.category.title()}")

        opp_tags = {str(t).lower() for t in (opp.tags or [])}
        matched_skills = [s.title() for s in prefs.skills if s.lower() in opp_tags]
        if matched_skills:
            reasons.append(f"Matches skills: {', '.join(matched_skills[:2])}")

        if not reasons:
            reasons.append("Matches your career preferences")

        return reasons[:3]
