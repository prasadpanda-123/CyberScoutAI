"""
Notification Delivery Service for CyberScout AI (Phase 7).

Coordinates outbox polling, quiet hours enforcement, multi-opportunity deduplication,
HTML/plain-text rendering, Brevo/SMTP delivery, and bounded retry failure tracking.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.notification_repository import NotificationRepository
from src.database.opportunity_repository import OpportunityRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.database.user_repository import UserRepository
from src.intelligence.quiet_hours import is_in_quiet_hours
from src.models.opportunity import Opportunity
from src.notifier.email_renderer import ModernEmailRenderer
from src.notifier.email_sender import EmailSender

logger = get_logger(__name__)


class NotificationService:
    """
    Decoupled notification dispatch service.
    Transmits pending outbox items via email/in-app channels without blocking harvesting.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        notification_repo: Optional[NotificationRepository] = None,
        preferences_repo: Optional[UserPreferencesRepository] = None,
        opportunity_repo: Optional[OpportunityRepository] = None,
        user_repo: Optional[UserRepository] = None,
        email_sender: Optional[EmailSender] = None,
        max_digest_cards: int = 20,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.notification_repo = notification_repo or NotificationRepository(db_manager=self.db_manager)
        self.preferences_repo = preferences_repo or UserPreferencesRepository(db_manager=self.db_manager)
        self.opportunity_repo = opportunity_repo or OpportunityRepository(db_manager=self.db_manager)
        self.user_repo = user_repo or UserRepository(db_manager=self.db_manager)
        self.email_sender = email_sender or EmailSender()
        self.max_digest_cards = max_digest_cards

    def dispatch_pending(self, delivery_mode: str = "all") -> Dict[str, Any]:
        """
        Processes pending outbox notifications for immediate and/or digest delivery.

        Args:
            delivery_mode: 'all', 'immediate', or 'digest'.

        Returns:
            Dictionary summary with sent, failed, deferred, and error metrics.
        """
        metrics: Dict[str, Any] = {
            "immediate_sent": 0,
            "digest_sent": 0,
            "emails_dispatched": 0,
            "deferred_quiet_hours": 0,
            "failed_count": 0,
            "errors": [],
        }

        # 1. Process Immediate Delivery
        if delivery_mode in ("all", "immediate"):
            try:
                imm_res = self._dispatch_immediate()
                metrics["immediate_sent"] += imm_res.get("items_sent", 0)
                metrics["emails_dispatched"] += imm_res.get("emails_sent", 0)
                metrics["deferred_quiet_hours"] += imm_res.get("deferred_quiet_hours", 0)
                metrics["failed_count"] += imm_res.get("failed_count", 0)
                if imm_res.get("errors"):
                    metrics["errors"].extend(imm_res["errors"])
            except Exception as e:
                logger.error(f"Failed immediate notification dispatch: {e}")
                metrics["errors"].append(str(e))

        # 2. Process Digest Delivery
        if delivery_mode in ("all", "digest"):
            try:
                dig_res = self._dispatch_digests()
                metrics["digest_sent"] += dig_res.get("items_sent", 0)
                metrics["emails_dispatched"] += dig_res.get("emails_sent", 0)
                metrics["failed_count"] += dig_res.get("failed_count", 0)
                if dig_res.get("errors"):
                    metrics["errors"].extend(dig_res["errors"])
            except Exception as e:
                logger.error(f"Failed digest notification dispatch: {e}")
                metrics["errors"].append(str(e))

        return metrics

    def _dispatch_immediate(self) -> Dict[str, Any]:
        """Processes pending immediate outbox entries."""
        res: Dict[str, Any] = {
            "items_sent": 0,
            "emails_sent": 0,
            "deferred_quiet_hours": 0,
            "failed_count": 0,
            "errors": [],
        }

        pending = self.notification_repo.get_pending_immediate(limit=100)
        if not pending:
            return res

        # Group by user_id
        by_user: Dict[int, List[Any]] = {}
        for item in pending:
            by_user.setdefault(item.user_id, []).append(item)

        for uid, items in by_user.items():
            user = self.user_repo.find_by_id(uid)
            if not user or not user.get("email"):
                continue

            recipient_email = user["email"]
            prefs = self.preferences_repo.get_preferences(uid)

            # Check email enabled
            if prefs and not prefs.email_notifications_enabled:
                # Mark sent or cancelled for email channel
                self.notification_repo.mark_sent([it.id for it in items], provider_message_id="suppressed-email-disabled")
                res["items_sent"] += len(items)
                continue

            # Check Quiet Hours
            if prefs and prefs.quiet_hours_enabled:
                if is_in_quiet_hours(
                    tz_str=prefs.timezone,
                    quiet_hours_start=prefs.quiet_hours_start,
                    quiet_hours_end=prefs.quiet_hours_end,
                    quiet_hours_enabled=True,
                ):
                    # Defer until outside quiet hours
                    res["deferred_quiet_hours"] += len(items)
                    logger.debug(f"Immediate alert for user {uid} deferred due to quiet hours.")
                    continue

            # Fetch opportunities and deduplicate
            opp_ids = [it.opportunity_id for it in items]
            opps = self._fetch_valid_opportunities(opp_ids)
            if not opps:
                self.notification_repo.mark_sent([it.id for it in items], provider_message_id="no-active-opps")
                continue

            item_ids = [it.id for it in items]
            self.notification_repo.mark_processing(item_ids)

            reasons_map = {
                it.opportunity_id: it.metadata_json.get("match_reasons", [])
                for it in items
                if it.metadata_json
            }

            try:
                html_body, plain_body = ModernEmailRenderer.render_digest(
                    opportunities=opps,
                    recipient_email=recipient_email,
                    digest_title="New Opportunity Alert",
                    period_label="Immediate Alert",
                    match_reasons_map=reasons_map,
                )
                subject = f"🎯 CyberScout Alert: {opps[0].title}" if len(opps) == 1 else f"🎯 CyberScout Alert: {len(opps)} New Opportunities"

                msg_id = self.email_sender.send_email(
                    html_content=html_body,
                    plain_content=plain_body,
                    subject=subject,
                    recipient=recipient_email,
                )
                self.notification_repo.mark_sent(item_ids, provider_message_id=msg_id)
                res["items_sent"] += len(items)
                res["emails_sent"] += 1
            except Exception as e:
                err_msg = str(e)
                logger.error(f"Failed to send immediate email to {recipient_email}: {err_msg}")
                self.notification_repo.mark_failed(item_ids, error=err_msg, retryable=True)
                res["failed_count"] += len(items)
                res["errors"].append(err_msg)

        return res

    def _dispatch_digests(self) -> Dict[str, Any]:
        """Processes pending digest outbox entries grouped by user."""
        res: Dict[str, Any] = {
            "items_sent": 0,
            "emails_sent": 0,
            "failed_count": 0,
            "errors": [],
        }

        user_ids = self.notification_repo.get_users_with_pending_digest()
        if not user_ids:
            return res

        for uid in user_ids:
            user = self.user_repo.find_by_id(uid)
            if not user or not user.get("email"):
                continue

            recipient_email = user["email"]
            prefs = self.preferences_repo.get_preferences(uid)

            if prefs and not prefs.email_notifications_enabled:
                pending_items = self.notification_repo.get_pending_digest_for_user(uid, limit=100)
                if pending_items:
                    self.notification_repo.mark_sent([it.id for it in pending_items], provider_message_id="suppressed-email-disabled")
                    res["items_sent"] += len(pending_items)
                continue

            # Fetch pending digest items for this user
            pending_items = self.notification_repo.get_pending_digest_for_user(uid, limit=50)
            if not pending_items:
                continue

            # Deduplicate opportunities: an opportunity MUST NOT appear twice in the same email
            seen_opp_ids: Set[str] = set()
            selected_items = []
            for it in pending_items:
                if it.opportunity_id not in seen_opp_ids:
                    seen_opp_ids.add(it.opportunity_id)
                    selected_items.append(it)
                else:
                    # Duplicate reference in same batch: mark as processed along with batch
                    selected_items.append(it)

            # Limit to max digest cards to prevent oversized emails
            # Only send up to max_digest_cards opportunities in this email run
            unique_opp_ids_ordered: List[str] = []
            for it in selected_items:
                if it.opportunity_id not in unique_opp_ids_ordered:
                    unique_opp_ids_ordered.append(it.opportunity_id)

            batch_opp_ids = unique_opp_ids_ordered[:self.max_digest_cards]
            items_to_deliver = [it for it in selected_items if it.opportunity_id in set(batch_opp_ids)]

            if not items_to_deliver:
                continue

            opps = self._fetch_valid_opportunities(batch_opp_ids)
            item_ids = [it.id for it in items_to_deliver]

            if not opps:
                self.notification_repo.mark_sent(item_ids, provider_message_id="no-active-opps")
                continue

            self.notification_repo.mark_processing(item_ids)

            reasons_map = {
                it.opportunity_id: it.metadata_json.get("match_reasons", [])
                for it in items_to_deliver
                if it.metadata_json
            }

            try:
                date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
                html_body, plain_body = ModernEmailRenderer.render_digest(
                    opportunities=opps,
                    recipient_email=recipient_email,
                    digest_title="Your Daily Intelligence Digest",
                    period_label="Daily Bulletin",
                    match_reasons_map=reasons_map,
                )
                subject = f"🎯 CyberScout Daily Digest: {len(opps)} Opportunities for You — {date_str}"

                msg_id = self.email_sender.send_email(
                    html_content=html_body,
                    plain_content=plain_body,
                    subject=subject,
                    recipient=recipient_email,
                )
                self.notification_repo.mark_sent(item_ids, provider_message_id=msg_id)
                res["items_sent"] += len(items_to_deliver)
                res["emails_sent"] += 1
            except Exception as e:
                err_msg = str(e)
                logger.error(f"Failed to send digest email to {recipient_email}: {err_msg}")
                self.notification_repo.mark_failed(item_ids, error=err_msg, retryable=True)
                res["failed_count"] += len(items_to_deliver)
                res["errors"].append(err_msg)

        return res

    def _fetch_valid_opportunities(self, opp_ids: List[str]) -> List[Opportunity]:
        """Fetches and deduplicates active opportunity objects by ID."""
        if not opp_ids:
            return []
        opps: List[Opportunity] = []
        seen = set()
        for oid in opp_ids:
            if oid in seen:
                continue
            seen.add(oid)
            try:
                opp = self.opportunity_repo.read_by_id(oid)
                if opp and getattr(opp, "quality_status", "") != "quarantined":
                    opps.append(opp)
            except Exception as e:
                logger.debug(f"Could not load opportunity {oid}: {e}")
        return opps

    def _deduplicate_cards(self, cards: List[Any]) -> List[Any]:
        """Deduplicates notification cards by opportunity_id keeping the first occurrence."""
        seen: Set[str] = set()
        deduped = []
        for c in cards:
            oid = getattr(c, "opportunity_id", None) or (c.get("opportunity_id") if isinstance(c, dict) else None)
            if oid and oid not in seen:
                seen.add(oid)
                deduped.append(c)
            elif not oid:
                deduped.append(c)
        return deduped
