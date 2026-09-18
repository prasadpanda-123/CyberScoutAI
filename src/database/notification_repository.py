"""
Notification Repository for CyberScout AI (Phase 7).

Manages persistence, atomic deduplication, outbox state transitions,
in-app notification feeds, and admin telemetry in PostgreSQL.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple, Union

from src.core.exceptions import RepositoryError
from src.core.logging import get_logger
from src.database.base_repository import row_to_dict
from src.database.connection import DatabaseManager
from src.models.enums import NotificationStatus
from src.models.notification_models import NotificationCardDTO, NotificationOutboxDTO

logger = get_logger(__name__)


class NotificationRepository:
    """DAO for managing NotificationOutbox records and user notification feeds."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def _normalize_uid(self, user_id: Any) -> Optional[str]:
        if user_id is None:
            return None
        try:
            import uuid
            return str(uuid.UUID(str(user_id).strip()))
        except (ValueError, TypeError, AttributeError):
            return None

    def enqueue_notification(self, record: NotificationOutboxDTO) -> Optional[str]:
        """
        Persists a single notification to the outbox with atomic database-level deduplication.
        Returns the record ID if newly queued, or None if already exists.
        """
        uid = self._normalize_uid(record.user_id)
        if uid is None or not record.opportunity_id or not record.deduplication_key:
            return None

        sql = """
        INSERT INTO "NotificationOutbox" (
            id, user_id, opportunity_id, event_type, notification_type,
            delivery_mode, change_fingerprint, deduplication_key, status,
            is_read, attempt_count, max_attempts, metadata_json, created_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, CURRENT_TIMESTAMP
        )
        ON CONFLICT (deduplication_key) DO NOTHING
        RETURNING id;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    sql,
                    (
                        record.id,
                        uid,
                        record.opportunity_id,
                        record.event_type.lower(),
                        record.notification_type.lower(),
                        record.delivery_mode.lower(),
                        record.change_fingerprint,
                        record.deduplication_key,
                        record.status.lower(),
                        record.is_read,
                        record.attempt_count,
                        record.max_attempts,
                        json.dumps(record.metadata_json or {}),
                    ),
                )
                row = cursor.fetchone()
                if row:
                    res_id = row[0] if isinstance(row, (tuple, list)) else row.get("id")
                    return str(res_id)
                return None
        except Exception as e:
            logger.error(f"Failed to enqueue notification '{record.deduplication_key}': {e}")
            raise RepositoryError(f"Failed to enqueue notification: {e}", original_exception=e)

    def enqueue_notifications_batch(self, records: List[NotificationOutboxDTO]) -> int:
        """
        Persists a batch of notifications with atomic database-level deduplication.
        Returns count of newly inserted outbox rows.
        """
        if not records:
            return 0

        sql = """
        INSERT INTO "NotificationOutbox" (
            id, user_id, opportunity_id, event_type, notification_type,
            delivery_mode, change_fingerprint, deduplication_key, status,
            is_read, attempt_count, max_attempts, metadata_json, created_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, CURRENT_TIMESTAMP
        )
        ON CONFLICT (deduplication_key) DO NOTHING;
        """
        valid_params = []
        for r in records:
            uid = self._normalize_uid(r.user_id)
            if uid is not None and r.opportunity_id and r.deduplication_key:
                valid_params.append((
                    r.id,
                    uid,
                    r.opportunity_id,
                    r.event_type.lower(),
                    r.notification_type.lower(),
                    r.delivery_mode.lower(),
                    r.change_fingerprint,
                    r.deduplication_key,
                    r.status.lower(),
                    r.is_read,
                    r.attempt_count,
                    r.max_attempts,
                    json.dumps(r.metadata_json or {}),
                ))

        if not valid_params:
            return 0

        try:
            inserted_count = 0
            with self.db_manager.transaction() as cursor:
                for params in valid_params:
                    cursor.execute(sql, params)
                    if cursor.rowcount > 0:
                        inserted_count += cursor.rowcount
            return inserted_count
        except Exception as e:
            logger.error(f"Failed batch enqueue of {len(records)} notifications: {e}")
            raise RepositoryError(f"Failed batch notification enqueue: {e}", original_exception=e)

    def _row_to_outbox_dto(self, row: Any) -> NotificationOutboxDTO:
        """Converts raw DB row to NotificationOutboxDTO."""
        d = row_to_dict(row)
        meta = d.get("metadata_json")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        return NotificationOutboxDTO(
            id=d["id"],
            user_id=str(d["user_id"]),
            opportunity_id=d["opportunity_id"],
            event_type=d["event_type"],
            notification_type=d.get("notification_type", "opportunity_alert"),
            delivery_mode=d.get("delivery_mode", "digest"),
            change_fingerprint=d.get("change_fingerprint"),
            deduplication_key=d["deduplication_key"],
            status=d.get("status", "pending"),
            is_read=bool(d.get("is_read", False)),
            read_at=str(d["read_at"]) if d.get("read_at") else None,
            attempt_count=int(d.get("attempt_count", 0)),
            max_attempts=int(d.get("max_attempts", 3)),
            last_error=d.get("last_error"),
            provider_message_id=d.get("provider_message_id"),
            created_at=str(d.get("created_at", "")),
            queued_at=str(d["queued_at"]) if d.get("queued_at") else None,
            sent_at=str(d["sent_at"]) if d.get("sent_at") else None,
            failed_at=str(d["failed_at"]) if d.get("failed_at") else None,
            metadata_json=meta or {},
        )

    def get_pending_immediate(self, limit: int = 100, max_attempts: int = 3) -> List[NotificationOutboxDTO]:
        """Retrieves pending immediate notifications eligible for delivery (bounded by max_attempts)."""
        sql = """
        SELECT * FROM "NotificationOutbox"
        WHERE status = 'pending' AND delivery_mode = 'immediate' AND attempt_count < %s
        ORDER BY created_at ASC
        LIMIT %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (max_attempts, max(1, min(limit, 500))))
                rows = cursor.fetchall()
                return [self._row_to_outbox_dto(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch pending immediate notifications: {e}")
            return []

    def get_users_with_pending_digest(self, max_attempts: int = 3) -> List[int]:
        """Returns list of distinct user IDs with pending digest notifications."""
        sql = """
        SELECT DISTINCT user_id FROM "NotificationOutbox"
        WHERE status = 'pending' AND delivery_mode = 'digest' AND attempt_count < %s
        ORDER BY user_id ASC;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (max_attempts,))
                rows = cursor.fetchall()
                uids = []
                for r in rows:
                    val = r[0] if isinstance(r, (tuple, list)) else r.get("user_id")
                    if val is not None:
                        uids.append(int(val))
                return uids
        except Exception as e:
            logger.error(f"Failed to fetch users with pending digest: {e}")
            return []

    def get_pending_digest_for_user(self, user_id: int, limit: int = 50, max_attempts: int = 3) -> List[NotificationOutboxDTO]:
        """Retrieves pending digest items for a specific user bounded by max_attempts."""
        uid = self._normalize_uid(user_id)
        if uid is None:
            return []

        sql = """
        SELECT * FROM "NotificationOutbox"
        WHERE user_id = %s AND status = 'pending' AND delivery_mode = 'digest' AND attempt_count < %s
        ORDER BY created_at ASC
        LIMIT %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (uid, max_attempts, max(1, min(limit, 200))))
                rows = cursor.fetchall()
                return [self._row_to_outbox_dto(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch pending digest for user {user_id}: {e}")
            return []

    def mark_processing(self, ids: Union[str, List[str]]) -> bool:
        """Transitions outbox records to PROCESSING state."""
        if isinstance(ids, str):
            ids = [ids]
        if not ids:
            return True
        sql = """
        UPDATE "NotificationOutbox"
        SET status = 'processing', queued_at = CURRENT_TIMESTAMP
        WHERE id = ANY(%s);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (ids,))
                return True
        except Exception as e:
            logger.error(f"Failed to mark notifications processing: {e}")
            return False

    def recover_stuck_processing(self, timeout_seconds: int = 900) -> int:
        """
        Recovers orphaned outbox items left in 'processing' state due to worker
        or application crashes. Resets eligible records back to 'pending' (incrementing
        attempt_count) or marks them 'failed' if attempts are exhausted.

        Returns:
            Number of recovered notification records.
        """
        sql = """
        UPDATE "NotificationOutbox"
        SET status = CASE 
                WHEN (attempt_count + 1) >= max_attempts THEN 'failed'
                ELSE 'pending'
            END,
            attempt_count = attempt_count + 1,
            last_error = 'Worker timeout / crash recovery (Phase 10 resilience)',
            failed_at = CASE
                WHEN (attempt_count + 1) >= max_attempts THEN CURRENT_TIMESTAMP
                ELSE failed_at
            END
        WHERE status = 'processing'
          AND (queued_at IS NULL OR queued_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 second'));
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (timeout_seconds,))
                recovered = cursor.rowcount
                if recovered > 0:
                    logger.warning(f"Recovered {recovered} stuck 'processing' notifications back to outbox.")
                return recovered
        except Exception as e:
            logger.error(f"Error recovering stuck processing notifications: {e}")
            return 0

    def mark_sent(self, ids: Union[str, List[str]], provider_message_id: Optional[str] = None) -> bool:
        """Transitions outbox records to SENT state with delivery timestamp and message ID."""
        if isinstance(ids, str):
            ids = [ids]
        if not ids:
            return True
        sql = """
        UPDATE "NotificationOutbox"
        SET status = 'sent',
            sent_at = CURRENT_TIMESTAMP,
            provider_message_id = COALESCE(%s, provider_message_id)
        WHERE id = ANY(%s);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (provider_message_id, ids))
                return True
        except Exception as e:
            logger.error(f"Failed to mark notifications sent: {e}")
            return False

    def mark_failed(self, ids: Union[str, List[str]], error: str, retryable: bool = True) -> bool:
        """
        Records delivery failure, increments attempt count, and sets FAILED status
        if max attempts reached or non-retryable.
        """
        if isinstance(ids, str):
            ids = [ids]
        if not ids:
            return True
        clean_err = (error or "Unknown delivery failure")[:500]

        sql = """
        UPDATE "NotificationOutbox"
        SET attempt_count = attempt_count + 1,
            last_error = %s,
            failed_at = CURRENT_TIMESTAMP,
            status = CASE 
                WHEN %s = FALSE OR (attempt_count + 1) >= max_attempts THEN 'failed'
                ELSE 'pending'
            END
        WHERE id = ANY(%s);
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (clean_err, retryable, ids))
                return True
        except Exception as e:
            logger.error(f"Failed to mark notifications failed: {e}")
            return False

    def get_user_notifications(
        self, user_id: int, unread_only: bool = False, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves in-app notification records for a user by left-joining NotificationOutbox with Opportunities.
        Strictly enforces user isolation. Returns a list of notification dictionary records.
        """
        uid = self._normalize_uid(user_id)
        if uid is None:
            return []

        where_clauses = ['n.user_id = %s']
        params: List[Any] = [uid]

        if unread_only:
            where_clauses.append('n.is_read = FALSE')

        where_sql = " AND ".join(where_clauses)

        data_sql = f"""
        SELECT n.id, n.user_id, n.opportunity_id, n.event_type, n.status, n.is_read,
               n.attempt_count, n.last_error, n.created_at, n.sent_at, n.failed_at,
               n.delivery_mode, n.metadata_json,
               COALESCE(o.title, 'Opportunity') as title,
               COALESCE(o.url, '#') as url,
               COALESCE(o.category, 'General') as category,
               o.provider, o.deadline, o.score, o.remote
        FROM "NotificationOutbox" n
        LEFT JOIN "Opportunities" o ON o.id = n.opportunity_id
        WHERE {where_sql}
        ORDER BY n.created_at DESC
        LIMIT %s OFFSET %s;
        """
        params.extend([max(1, min(limit, 100)), max(0, offset)])

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(data_sql, tuple(params))
                rows = cursor.fetchall()
                results: List[Dict[str, Any]] = []

                for r in rows:
                    d = row_to_dict(r)
                    meta = d.get("metadata_json") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}

                    deadline_val = d.get("deadline")
                    if hasattr(deadline_val, "isoformat"):
                        deadline_str = deadline_val.isoformat()[:10]
                    else:
                        deadline_str = str(deadline_val)[:10] if deadline_val else None

                    event_type_str = d.get("event_type", "NEW")
                    if hasattr(event_type_str, "value"):
                        event_type_str = event_type_str.value
                    elif isinstance(event_type_str, str):
                        event_type_str = event_type_str.upper()

                    status_str = d.get("status", "pending")
                    if hasattr(status_str, "value"):
                        status_str = status_str.value
                    elif isinstance(status_str, str):
                        status_str = status_str.upper()

                    results.append({
                        "id": d["id"],
                        "user_id": d["user_id"],
                        "opportunity_id": d["opportunity_id"],
                        "event_type": event_type_str,
                        "status": status_str,
                        "is_read": bool(d.get("is_read", False)),
                        "attempt_count": int(d.get("attempt_count", 0)),
                        "last_error": d.get("last_error"),
                        "created_at": str(d.get("created_at", "")),
                        "sent_at": str(d.get("sent_at", "")) if d.get("sent_at") else None,
                        "failed_at": str(d.get("failed_at", "")) if d.get("failed_at") else None,
                        "delivery_mode": d.get("delivery_mode", "digest"),
                        "title": d.get("title") or "Opportunity",
                        "url": d.get("url") or "#",
                        "category": d.get("category") or "General",
                        "provider": d.get("provider"),
                        "deadline": deadline_str,
                        "score": float(d.get("score", 0.0) or 0.0),
                        "remote": bool(d.get("remote", False)),
                        "match_reasons": meta.get("match_reasons") or [],
                    })
                return results
        except Exception as e:
            logger.error(f"Failed to fetch notifications for user {user_id}: {e}")
            return []

    def mark_as_read(self, notification_id: str, user_id: int) -> bool:
        """Marks a notification as read, enforcing strict user ownership."""
        uid = self._normalize_uid(user_id)
        if uid is None or not notification_id:
            return False

        sql = """
        UPDATE "NotificationOutbox"
        SET is_read = TRUE, read_at = CURRENT_TIMESTAMP
        WHERE id = %s AND user_id = %s;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (notification_id, uid))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to mark notification as read: {e}")
            return False

    def mark_all_as_read(self, user_id: int) -> int:
        """Marks all notifications as read for a specific user."""
        uid = self._normalize_uid(user_id)
        if uid is None:
            return 0

        sql = """
        UPDATE "NotificationOutbox"
        SET is_read = TRUE, read_at = CURRENT_TIMESTAMP
        WHERE user_id = %s AND is_read = FALSE;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (uid,))
                return cursor.rowcount if cursor.rowcount > 0 else 0
        except Exception as e:
            logger.error(f"Failed to mark all notifications as read for user {user_id}: {e}")
            return 0

    def get_admin_observability_stats(self) -> Dict[str, Any]:
        """
        Returns high-level telemetry and status breakdown of NotificationOutbox
        for admin operational observability.
        """
        sql = """
        SELECT status, COUNT(*) as cnt
        FROM "NotificationOutbox"
        GROUP BY status;
        """
        recent_failures_sql = """
        SELECT id, user_id, opportunity_id, event_type, attempt_count, last_error, failed_at
        FROM "NotificationOutbox"
        WHERE status = 'failed' OR last_error IS NOT NULL
        ORDER BY COALESCE(failed_at, created_at) DESC
        LIMIT 10;
        """
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                status_counts: Dict[str, int] = {
                    "pending": 0,
                    "processing": 0,
                    "sent": 0,
                    "failed": 0,
                    "cancelled": 0,
                }
                total = 0
                for r in rows:
                    d = row_to_dict(r)
                    st = str(d.get("status", "")).lower()
                    cnt = int(d.get("cnt", 0))
                    if st in status_counts:
                        status_counts[st] = cnt
                    total += cnt

                cursor.execute(recent_failures_sql)
                fail_rows = cursor.fetchall()
                recent_failures = [row_to_dict(fr) for fr in fail_rows]

                return {
                    "total": total,
                    "total_notifications": total,
                    "pending": status_counts["pending"],
                    "processing": status_counts["processing"],
                    "sent": status_counts["sent"],
                    "failed": status_counts["failed"],
                    "cancelled": status_counts["cancelled"],
                    "recent_failures": recent_failures,
                }
        except Exception as e:
            logger.error(f"Failed to fetch admin outbox stats: {e}")
            return {
                "total": 0,
                "total_notifications": 0,
                "pending": 0,
                "processing": 0,
                "sent": 0,
                "failed": 0,
                "cancelled": 0,
                "recent_failures": [],
            }
