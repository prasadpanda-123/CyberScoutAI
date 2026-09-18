"""
User Notifications and Delivery Management Routes for CyberScout AI.
Implements Phase 7 SSR notification inbox, preference controls, CSRF validation, and user isolation.
"""

from datetime import datetime, timezone
import hmac
import logging
from flask import Blueprint, flash, redirect, render_template, request, session, url_for, jsonify
from src.auth.decorators import login_required
from src.database.connection import DatabaseManager
from src.database.notification_repository import NotificationRepository
from src.database.user_preferences_repository import UserPreferencesRepository
from src.database.scheduler_repository import SchedulerRepository
from src.database.audit_log_repository import AuditLogRepository
from src.models.recommendation_models import UserPreferencesDTO

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications_ui", __name__)


def _verify_csrf(req) -> bool:
    """Validates CSRF token from form, JSON body, or X-CSRF-Token header."""
    if req.is_json and req.json:
        submitted = req.json.get("csrf_token")
    else:
        submitted = req.form.get("csrf_token") or req.headers.get("X-CSRF-Token")
    expected = session.get("user_csrf_token") or session.get("csrf_token")
    if not expected or not submitted:
        return False
    return hmac.compare_digest(str(submitted), str(expected))


def _get_client_ip(req) -> str:
    """Extracts client IP safely considering proxies."""
    forwarded = req.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return req.remote_addr or "127.0.0.1"


@notifications_bp.route("/notifications", methods=["GET"])
@login_required
def index():
    """Renders user-facing notification preferences and in-app alerts inbox."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth_ui.login"))

    db_mgr = DatabaseManager()
    notif_repo = NotificationRepository(db_manager=db_mgr)
    pref_repo = UserPreferencesRepository(db_manager=db_mgr)
    sched_repo = SchedulerRepository(db_manager=db_mgr)

    # 1. Fetch user notifications inbox
    notifications = notif_repo.get_user_notifications(user_id=user_id, limit=50)
    unread_count = sum(1 for n in notifications if not n.get("is_read"))

    # 2. Fetch user preferences
    preferences = pref_repo.get_preferences(user_id=user_id) or UserPreferencesDTO()

    # 3. Scheduler state & email info
    state = sched_repo.get_state()
    user_email = session.get("email") or "Registered Email"

    email_info = {
        "status": "Active" if preferences.email_notifications_enabled else "Paused",
        "frequency": f"{preferences.delivery_mode.capitalize()} (Digest: {preferences.digest_frequency})",
        "recipient_email": user_email,
        "last_delivery": state.get("last_email_sent") or "Active (Awaiting next scheduled cycle)",
        "attachments": "Modern HTML Opportunity Bulletins",
    }

    return render_template(
        "notifications.html",
        active_page="notifications",
        email_info=email_info,
        notifications=notifications,
        unread_count=unread_count,
        preferences=preferences,
    )


@notifications_bp.route("/notifications/mark-read", methods=["POST"])
@login_required
def mark_read():
    """Marks a single notification as read for the authenticated user (CSRF-protected)."""
    if not _verify_csrf(request):
        if request.is_json:
            return jsonify({"status": "failed", "error": "CSRF verification failed"}), 403
        flash("Security validation failed (invalid CSRF token).", "danger")
        return redirect(url_for("notifications_ui.index"))

    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth_ui.login"))

    notif_id = (request.json.get("notification_id") if request.is_json and request.json 
                else request.form.get("notification_id"))

    if not notif_id:
        if request.is_json:
            return jsonify({"status": "failed", "error": "Notification ID is required"}), 400
        flash("Notification ID required.", "warning")
        return redirect(url_for("notifications_ui.index"))

    db_mgr = DatabaseManager()
    notif_repo = NotificationRepository(db_manager=db_mgr)
    success = notif_repo.mark_as_read(notification_id=str(notif_id), user_id=user_id)

    if request.is_json:
        return jsonify({"status": "success" if success else "not_found", "id": notif_id})

    if success:
        flash("Notification marked as read.", "success")
    else:
        flash("Notification could not be updated.", "warning")
    return redirect(url_for("notifications_ui.index"))


@notifications_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    """Marks all notifications as read for the authenticated user (CSRF-protected)."""
    if not _verify_csrf(request):
        if request.is_json:
            return jsonify({"status": "failed", "error": "CSRF verification failed"}), 403
        flash("Security validation failed (invalid CSRF token).", "danger")
        return redirect(url_for("notifications_ui.index"))

    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth_ui.login"))

    db_mgr = DatabaseManager()
    notif_repo = NotificationRepository(db_manager=db_mgr)
    count = notif_repo.mark_all_as_read(user_id=user_id)

    if request.is_json:
        return jsonify({"status": "success", "updated_count": count})

    flash(f"Marked {count} notifications as read.", "success")
    return redirect(url_for("notifications_ui.index"))


@notifications_bp.route("/notifications/preferences", methods=["POST"])
@login_required
def update_preferences():
    """Updates user notification delivery preferences with server validation and CSRF protection."""
    if not _verify_csrf(request):
        flash("Security validation failed (invalid CSRF token).", "danger")
        return redirect(url_for("notifications_ui.index"))

    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth_ui.login"))

    db_mgr = DatabaseManager()
    pref_repo = UserPreferencesRepository(db_manager=db_mgr)
    audit_repo = AuditLogRepository()

    existing_prefs = pref_repo.get_preferences(user_id=user_id) or UserPreferencesDTO()

    # Form values
    email_enabled = request.form.get("email_notifications_enabled") == "on"
    in_app_enabled = request.form.get("in_app_notifications_enabled") == "on"
    notify_new = request.form.get("notify_new_opportunities") == "on"
    notify_updated = request.form.get("notify_meaningful_updates") == "on"
    notify_reopened = request.form.get("notify_reopened_opportunities") == "on"

    delivery_mode = request.form.get("delivery_mode", "IMMEDIATE").strip().upper()
    if delivery_mode not in ("IMMEDIATE", "DIGEST"):
        delivery_mode = "IMMEDIATE"

    digest_frequency = request.form.get("digest_frequency", "DAILY").strip().upper()
    if digest_frequency not in ("DAILY", "WEEKLY"):
        digest_frequency = "DAILY"

    quiet_hours_enabled = request.form.get("quiet_hours_enabled") == "on"
    quiet_start = request.form.get("quiet_hours_start", "22:00").strip()
    quiet_end = request.form.get("quiet_hours_end", "08:00").strip()
    user_tz = request.form.get("timezone", "UTC").strip() or "UTC"

    # Merge into UserPreferencesDTO preserving existing career preferences
    existing_prefs.email_notifications_enabled = email_enabled
    existing_prefs.in_app_notifications_enabled = in_app_enabled
    existing_prefs.notify_new_opportunities = notify_new
    existing_prefs.notify_meaningful_updates = notify_updated
    existing_prefs.notify_reopened_opportunities = notify_reopened
    existing_prefs.delivery_mode = delivery_mode
    existing_prefs.digest_frequency = digest_frequency
    existing_prefs.quiet_hours_enabled = quiet_hours_enabled
    existing_prefs.quiet_hours_start = quiet_start
    existing_prefs.quiet_hours_end = quiet_end
    existing_prefs.timezone = user_tz

    try:
        pref_repo.save_preferences(user_id=user_id, preferences=existing_prefs)
        audit_repo.log_event(
            category="USER_PROFILE",
            action="NOTIFICATION_PREFERENCES_UPDATED",
            status="SUCCESS",
            user_id=user_id,
            username=session.get("username"),
            source_ip=_get_client_ip(request),
            details=f"Delivery mode: {delivery_mode}, Email: {email_enabled}, In-app: {in_app_enabled}",
        )
        flash("Notification preferences updated successfully.", "success")
    except Exception as e:
        logger.error(f"Failed to update notification preferences for user {user_id}: {e}")
        flash("Failed to update notification preferences.", "danger")

    return redirect(url_for("notifications_ui.index"))
