"""
Dedicated Administrative Portal Routes (Phase 1 & Phase 3) for CyberScout AI v2.2.

Isolates all administrative views under `/admin/*` protected by `@admin_required`.
"""

import os
from pathlib import Path
import time
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for, send_from_directory, abort

from dashboard.services.analytics_service import AnalyticsService
from dashboard.services.api_service import APIService
from dashboard.services.dashboard_service import DashboardService
from dashboard.services.statistics_service import StatisticsService
from src.auth.admin_auth import AdminSecurityManager
from src.auth.decorators import admin_required
from src.core.constants import CONFIG_DIR, REPORTS_DIR
from src.core.rss_diagnostics import RSSDiagnosticsManager
from src.core.version import get_version_info
from src.database.admin_repository import AdminRepository
from src.database.audit_log_repository import AuditLogRepository
from src.database.log_repository import LogRepository
from src.database.user_repository import UserRepository
from src.utils.ip_utils import get_client_ip
from src.utils.pagination_utils import parse_pagination
from src.utils.url_utils import is_safe_internal_url

admin_bp = Blueprint("admin_ui", __name__, url_prefix="/admin")

user_repo = UserRepository()
admin_repo = AdminRepository()
audit_repo = AuditLogRepository()
log_repo = LogRepository()
dash_service = DashboardService()
stats_service = StatisticsService()
api_service = APIService()


@admin_bp.before_request
def ensure_csrf_token():
    """Ensures a CSRF token is present in the admin session."""
    try:
        if "admin_csrf_token" not in session:
            session["admin_csrf_token"] = AdminSecurityManager.generate_csrf_token()
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).warning(f"Error generating admin_csrf_token: {e}")


@admin_bp.route("", methods=["GET"])
@admin_bp.route("/", methods=["GET"])
def admin_root():
    """Redirects /admin and /admin/ entrypoints to admin dashboard or admin login."""
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_ui.admin_dashboard"))
    return redirect(url_for("admin_ui.admin_login"))


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """
    Dedicated Admin Login Portal.
    Only allows users with role  'Administrator' to authenticate.
    """
    try:
        # If already authenticated as admin, redirect safely to next or admin dashboard
        if session.get("admin_authenticated"):
            raw_next = request.form.get("next") or request.args.get("next")
            target = (raw_next if (raw_next and is_safe_internal_url(raw_next)) else None) or url_for("admin_ui.admin_dashboard")
            return redirect(target)

        client_ip = get_client_ip(request)

        if request.method == "POST":
            is_json = request.is_json or (request.headers.get("Accept") == "application/json" and request.get_json(silent=True) is not None)
            json_data = request.get_json(silent=True) if is_json else None

            if is_json and json_data:
                identifier = (
                    json_data.get("admin_username", "").strip()
                    or json_data.get("identifier", "").strip()
                    or json_data.get("username", "").strip()
                )
                password = (
                    json_data.get("admin_password", "").strip()
                    or json_data.get("password", "").strip()
                )
                csrf_token = (json_data.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()
                raw_next = json_data.get("next") or request.args.get("next")
            else:
                identifier = (
                    request.form.get("admin_username", "").strip()
                    or request.form.get("identifier", "").strip()
                    or request.form.get("username", "").strip()
                )
                password = (
                    request.form.get("admin_password", "").strip()
                    or request.form.get("password", "").strip()
                )
                csrf_token = (request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()
                raw_next = request.form.get("next") or request.args.get("next")

            next_url: str = raw_next if (raw_next and is_safe_internal_url(raw_next)) else url_for("admin_ui.admin_dashboard")

            # 1. Validate CSRF Token
            if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
                if is_json:
                    return jsonify({"status": "failed", "error": "CSRF validation failed. Please try again."}), 400
                flash("CSRF validation failed. Please try again.", "danger")
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN", "FAILED", username=identifier, source_ip=client_ip, details="CSRF token mismatch")
                except Exception:
                    pass
                return render_template("admin/admin_login.html", next=next_url)

            # 2. Atomically reserve a shared login attempt before password verification.
            try:
                login_attempt_allowed = AdminSecurityManager.consume_login_attempt(client_ip, identifier)
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).error(f"Distributed administrator login throttle is unavailable: {e}")
                if is_json:
                    return jsonify({"status": "failed", "error": "Authentication is temporarily unavailable."}), 503
                flash("Authentication is temporarily unavailable. Please try again shortly.", "danger")
                return render_template("admin/admin_login.html", next=next_url), 503

            if not login_attempt_allowed:
                if is_json:
                    return jsonify({"status": "failed", "error": "Account locked due to 5 consecutive failed login attempts. Please wait 15 minutes."}), 429
                flash("Account locked due to 5 consecutive failed login attempts. Please wait 15 minutes.", "danger")
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN", "LOCKED_OUT", username=identifier, source_ip=client_ip, details="Attempt during lockout period")
                except Exception:
                    pass
                return render_template("admin/admin_login.html", next=next_url)

            # 3. Authenticate Administrator against Admins table
            db_outage = False
            try:
                user = admin_repo.authenticate(identifier, password)
            except Exception as e:
                from src.core.logging import get_logger
                err_str = str(e).lower()
                if any(term in err_str for term in ("connection", "could not connect", "timeout", "pool", "network", "operationalerror", "server closed")):
                    get_logger(__name__).error(f"Database outage during administrator authentication: {e}")
                    db_outage = True
                else:
                    get_logger(__name__).error(f"Administrator authentication error: {e}")
                user = None

            if db_outage:
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN_ERROR", "SERVICE_UNAVAILABLE", username=identifier, source_ip=client_ip, details="Database unavailable during administrator authentication")
                except Exception:
                    pass
                if is_json:
                    return jsonify({"status": "failed", "error": "Database service temporarily unavailable."}), 503
                flash("Database service temporarily unavailable. Please try again in a few moments.", "danger")
                return render_template("admin/admin_login.html", next=next_url), 503

            if not user:
                if is_json:
                    return jsonify({"status": "failed", "error": "Invalid administrator credentials."}), 401
                flash("Invalid administrator credentials.", "danger")
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN", "FAILED", username=identifier, source_ip=client_ip, details="Invalid credentials")
                except Exception:
                    pass
                return render_template("admin/admin_login.html", next=next_url)

            # 4. Role Authorization Check: Admin role permitted
            user_role = user.get("role") or user.get("account_type") or "Admin"
            if str(user_role).lower() not in ("admin", "super admin", "administrator"):
                if is_json:
                    return jsonify({"status": "failed", "error": "Access Denied: Standard user accounts cannot authenticate through the Administrator Portal."}), 403
                flash("Access Denied: Standard user accounts cannot authenticate through the Administrator Portal.", "danger")
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN", "DENIED", username=user["username"], source_ip=client_ip, details=f"Non-admin role '{user_role}' attempted admin login")
                except Exception:
                    pass
                return render_template("admin/admin_login.html", next=next_url)

            # 5. Password Verified -> Generate 6-digit OTP & Store Pending MFA State in Server Memory
            otp_code = AdminSecurityManager.generate_otp_code()
            otp_hash = AdminSecurityManager.hash_otp_code(otp_code)
            expires_at = int(time.time()) + 300  # 5 minutes validity

            try:
                pending_token = AdminSecurityManager.store_pending_mfa(
                    user_id=user["id"],
                    username=user["username"],
                    email=user["email"],
                    role=user.get("role") or "Admin",
                    otp_hash=otp_hash,
                    expires_at=expires_at,
                    next_url=next_url,
                )
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).error("Unable to start administrator MFA: %s", type(e).__name__)
                if is_json:
                    return jsonify({
                        "status": "failed",
                        "error": "Authentication is temporarily unavailable. Please try again.",
                    }), 503
                flash("Authentication is temporarily unavailable. Please try again.", "danger")
                return render_template("admin/admin_login.html", next=next_url), 503
            session["admin_pending_token"] = pending_token

            # Transmit OTP Code via Production Email Service
            try:
                from src.notifier.email_sender import EmailSender
                sender = EmailSender()
                subject = "CyberScout AI — Administrator Verification Code"
                plain_body = f"Hello {user['username']},\n\nYour 6-digit administrator verification code is:\n\n{otp_code}\n\nThis code is valid for 5 minutes. Do not share this code with anyone.\n\nCyberScout AI Security"
                html_body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif; background-color:#0f172a; color:#f8fafc; padding:30px;">
                <div style="max-width:500px; margin:0 auto; background-color:#1e293b; padding:30px; border-radius:10px; border:1px solid #334155;">
                  <h2 style="color:#ef4444; margin-top:0;">CyberScout AI Security</h2>
                  <p>Administrator Multi-Factor Authentication Code:</p>
                  <div style="background-color:#0f172a; border:1px solid #ef4444; color:#ef4444; font-size:32px; font-weight:bold; letter-spacing:5px; text-align:center; padding:15px; border-radius:8px; margin:20px 0; user-select:all;">{otp_code}</div>
                  <p style="font-size:13px; color:#94a3b8;">This code is valid for 5 minutes. If you did not request this login, please notify system administrators immediately.</p>
                </div>
                </body></html>"""
                
                admin_email = user.get("email") or os.getenv("EMAIL_TO") or "admin@cyberscout.ai"
                from src.core.logging import get_logger
                logger = get_logger(__name__)
                logger.info(f"Admin OTP email requested for administrator: '{user['username']}'")
                
                msg_id = sender.send_email(
                    html_content=html_body,
                    plain_content=plain_body,
                    subject=subject,
                    recipient=admin_email,
                )
                logger.info(f"Brevo accepted email message (Message-ID: {msg_id})")
                try:
                    audit_repo.log_event("MFA", "OTP_GENERATED", "SUCCESS", username=user["username"], source_ip=client_ip, details=f"OTP code dispatched via Brevo (msg_id={msg_id})")
                except Exception:
                    pass
                if is_json:
                    return jsonify({"status": "success", "mfa_required": True, "message": "Verification code sent to your registered email.", "redirect": "/admin/verify-otp"}), 200
                flash("Verification code sent to your registered email.", "info")
                return redirect(url_for("admin_ui.admin_verify_otp"))
            except Exception as e:
                AdminSecurityManager.clear_pending_mfa(pending_token)
                session.pop("admin_pending_token", None)
                from src.core.logging import get_logger
                get_logger(__name__).error(f"Brevo API rejected OTP email: {e}")
                try:
                    audit_repo.log_event("MFA", "OTP_GENERATED", "DISPATCH_FAILED", username=user["username"], source_ip=client_ip, details=f"Failed to dispatch OTP email for admin '{user['username']}'")
                except Exception:
                    pass
                if is_json:
                    return jsonify({"status": "failed", "error": "We couldn't send the verification code. Please try again or contact the administrator."}), 500
                flash("We couldn't send the verification code. Please try again or contact the administrator.", "danger")
                return render_template("admin/admin_login.html", next=next_url)

        raw_next_get = request.args.get("next", "")
        safe_next_get = raw_next_get if is_safe_internal_url(raw_next_get) else ""
        if request.args.get("legacy") == "1":
            return render_template("admin/admin_login.html", next=safe_next_get)
        return render_template("react_shell.html")
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Error rendering admin_login page: {e}")
        raw_next_err = request.args.get("next", "")
        safe_next_err = raw_next_err if is_safe_internal_url(raw_next_err) else ""
        if request.args.get("legacy") == "1":
            return render_template("admin/admin_login.html", next=safe_next_err)
        return render_template("react_shell.html")


@admin_bp.route("/verify-otp", methods=["GET", "POST"])
def admin_verify_otp():
    """
    Administrator OTP Verification (MFA) endpoint (Phases 6 - 8).
    Requires 6-digit numeric OTP code sent to admin's email.
    """
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_ui.admin_dashboard"))

    pending_token = session.get("admin_pending_token")
    try:
        mfa_state = AdminSecurityManager.get_pending_mfa(pending_token)
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error("Unable to load administrator MFA state: %s", type(e).__name__)
        if request.is_json:
            return jsonify({
                "status": "failed",
                "error": "Authentication is temporarily unavailable. Please try again.",
            }), 503
        if request.args.get("legacy") == "1":
            return render_template("admin/admin_verify_otp.html", username=""), 503
        return render_template("react_shell.html"), 503

    if not mfa_state:
        # Fallback for legacy session structures
        if session.get("admin_pending_user_id") and session.get("admin_pending_otp_hash"):
            mfa_state = {
                "user_id": session.get("admin_pending_user_id"),
                "username": session.get("admin_pending_username"),
                "role": session.get("admin_pending_role", "Admin"),
                "email": session.get("admin_pending_email"),
                "otp_hash": session.get("admin_pending_otp_hash"),
                "expires_at": session.get("admin_pending_otp_expires_at", 0),
                "attempts": session.get("admin_pending_otp_attempts", 0),
                "next_url": session.get("admin_pending_next", url_for("admin_ui.admin_dashboard")),
            }

    if not mfa_state or not pending_token:
        flash("No pending authentication session. Please log in.", "warning")
        return redirect(url_for("admin_ui.admin_login"))

    user_id = mfa_state.get("user_id")
    username = str(mfa_state.get("username") or "")
    role = str(mfa_state.get("role") or "Administrator")
    otp_hash = str(mfa_state.get("otp_hash") or "")
    expires_at = int(mfa_state.get("expires_at") or 0)
    next_url = str(mfa_state.get("next_url") or url_for("admin_ui.admin_dashboard"))
    pending_token_str = str(pending_token)

    client_ip = get_client_ip(request)
    now = int(time.time())

    # Check 5-minute expiration window
    if expires_at <= 0 or now > expires_at:
        AdminSecurityManager.clear_pending_mfa(pending_token_str)
        session.pop("admin_pending_token", None)
        session.pop("admin_last_resend_at", None)
        audit_repo.log_event("MFA", "OTP_EXPIRED", "FAILED", username=username, source_ip=client_ip, details=f"OTP code expired for admin '{username}'")
        flash("Verification code has expired (valid for 5 minutes). Please log in again.", "danger")
        return redirect(url_for("admin_ui.admin_login"))

    if request.method == "POST":
        is_json = request.is_json or (request.headers.get("Accept") == "application/json" and request.get_json(silent=True) is not None)
        json_data = request.get_json(silent=True) if is_json else None

        if is_json and json_data:
            action = (json_data.get("action") or "").strip()
            csrf_token = (json_data.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()
            raw_code = (json_data.get("otp") or json_data.get("otp_code") or "").strip()
        else:
            action = request.form.get("action", "").strip()
            csrf_token = (request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()
            raw_code = request.form.get("otp_code", "")

        if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
            if is_json:
                return jsonify({"status": "failed", "error": "CSRF validation failed."}), 400
            flash("CSRF validation failed.", "danger")
            return render_template("admin/admin_verify_otp.html", username=username)

        # Handle Resend OTP Action
        if action == "resend":
            last_resend = session.get("admin_last_resend_at", 0)
            if now - last_resend < 30:
                cooldown_remaining = 30 - (now - last_resend)
                if is_json:
                    return jsonify({"status": "failed", "error": f"Please wait {cooldown_remaining} seconds before requesting a new code."}), 429
                flash(f"Please wait {cooldown_remaining} seconds before requesting a new code.", "warning")
                return render_template("admin/admin_verify_otp.html", username=username)

            new_otp_code = AdminSecurityManager.generate_otp_code()
            new_otp_hash = AdminSecurityManager.hash_otp_code(new_otp_code)
            new_expires_at = now + 300

            AdminSecurityManager.update_pending_mfa_otp(pending_token_str, new_otp_hash, new_expires_at)
            session["admin_last_resend_at"] = now
            session.modified = True

            try:
                from src.notifier.email_sender import EmailSender
                sender = EmailSender()
                subject = "CyberScout AI — Administrator Verification Code"
                plain_body = f"Hello {username},\n\nYour new 6-digit administrator verification code is:\n\n{new_otp_code}\n\nThis code is valid for 5 minutes. Do not share this code with anyone.\n\nCyberScout AI Security"
                html_body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif; background-color:#0f172a; color:#f8fafc; padding:30px;">
                <div style="max-width:500px; margin:0 auto; background-color:#1e293b; padding:30px; border-radius:10px; border:1px solid #334155;">
                  <h2 style="color:#ef4444; margin-top:0;">CyberScout AI Security</h2>
                  <p>Administrator Multi-Factor Authentication Code:</p>
                  <div style="background-color:#0f172a; border:1px solid #ef4444; color:#ef4444; font-size:32px; font-weight:bold; letter-spacing:5px; text-align:center; padding:15px; border-radius:8px; margin:20px 0; user-select:all;">{new_otp_code}</div>
                  <p style="font-size:13px; color:#94a3b8;">This code is valid for 5 minutes. If you did not request this login, please notify system administrators immediately.</p>
                </div>
                </body></html>"""
                admin_email = mfa_state.get("email") or os.getenv("EMAIL_TO") or "admin@cyberscout.ai"
                msg_id = sender.send_email(
                    html_content=html_body,
                    plain_content=plain_body,
                    subject=subject,
                    recipient=admin_email,
                )
                try:
                    audit_repo.log_event("MFA", "OTP_RESENT", "SUCCESS", username=username, source_ip=client_ip, details=f"New OTP code dispatched via Brevo (msg_id={msg_id})")
                except Exception:
                    pass
                if is_json:
                    return jsonify({"status": "success", "message": "A new verification code has been sent to your registered email."}), 200
                flash("A new verification code has been sent to your registered email.", "info")
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).error(f"Failed to resend admin OTP: {e}")
                if is_json:
                    return jsonify({"status": "failed", "error": "We couldn't resend the verification code. Please try again later."}), 500
                flash("We couldn't resend the verification code. Please try again later.", "danger")

            return render_template("admin/admin_verify_otp.html", username=username)

        # Standard OTP Verification
        import re
        otp_code = re.sub(r"[\s\-\u200b\u00a0\ufeff]", "", raw_code.strip())

        # Check hash BEFORE incrementing failed attempts
        if AdminSecurityManager.verify_otp_code(otp_code, otp_hash):
            # Single-use OTP: Clear pending MFA state
            AdminSecurityManager.clear_pending_mfa(pending_token_str)
            session.pop("admin_pending_token", None)
            session.pop("admin_last_resend_at", None)

            # Issue full administrator session
            AdminSecurityManager.reset_failed_attempts(client_ip, username)
            session.clear()
            session.permanent = True
            session["admin_authenticated"] = True
            session["admin_user_id"] = user_id
            session["admin_username"] = username
            session["admin_role"] = role
            session["role"] = role
            session["admin_csrf_token"] = AdminSecurityManager.generate_csrf_token()
            session["admin_login_at"] = int(time.time())
            session.modified = True

            audit_repo.log_event("MFA", "OTP_VERIFIED", "SUCCESS", username=username, source_ip=client_ip, details=f"OTP verified successfully for admin '{username}'")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "SUCCESS", username=username, source_ip=client_ip, details=f"Administrator MFA Session Established for '{username}'")
            safe_redirect = next_url if is_safe_internal_url(next_url) else url_for("admin_ui.admin_dashboard")
            if is_json:
                return jsonify({
                    "status": "success",
                    "message": f"MFA Verification Successful! Welcome to the Administrator Portal, {username}.",
                    "admin_authenticated": True,
                    "redirect": safe_redirect,
                }), 200
            flash(f"MFA Verification Successful! Welcome to the Administrator Portal, {username}.", "success")
            return redirect(safe_redirect)
        else:
            # ONLY increment attempts on failed verification!
            attempts = AdminSecurityManager.increment_pending_mfa_attempts(pending_token_str)
            if attempts >= 5:
                AdminSecurityManager.clear_pending_mfa(pending_token_str)
                session.pop("admin_pending_token", None)
                session.pop("admin_last_resend_at", None)
                audit_repo.log_event("MFA", "OTP_LOCKOUT", "FAILED", username=username, source_ip=client_ip, details=f"Exceeded 5 OTP attempts for admin '{username}'")
                if is_json:
                    return jsonify({"status": "failed", "error": "Maximum OTP verification attempts exceeded. Please log in again."}), 429
                flash("Maximum OTP verification attempts exceeded. Please log in again.", "danger")
                return redirect(url_for("admin_ui.admin_login"))

            remaining = max(0, 5 - attempts)
            audit_repo.log_event("MFA", "OTP_VERIFY_FAILED", "FAILED", username=username, source_ip=client_ip, details=f"Invalid OTP code (attempt {attempts}/5) for admin '{username}'")
            if is_json:
                return jsonify({"status": "failed", "error": f"Invalid verification code. {remaining} attempt(s) remaining."}), 401
            flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "danger")

    if request.args.get("legacy") == "1":
        return render_template("admin/admin_verify_otp.html", username=username)
    return render_template("react_shell.html")


@admin_bp.route("/logout", methods=["POST"])
def admin_logout():
    """Clears administrative session namespace using a CSRF-protected POST."""
    client_ip = get_client_ip(request)
    submitted_csrf = (
        request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
        or request.form.get("csrf_token", "")
    )
    expected_csrf = session.get("admin_csrf_token")
    if not AdminSecurityManager.verify_csrf_token(expected_csrf, submitted_csrf.strip() if isinstance(submitted_csrf, str) else ""):
        return jsonify({"status": "failed", "error": "CSRF validation failed."}), 400
    admin_user = session.get("admin_username")

    if admin_user:
        audit_repo.log_event("AUTH", "ADMIN_LOGOUT", "SUCCESS", username=admin_user, source_ip=client_ip, details=f"Admin '{admin_user}' logged out")

    session.pop("admin_authenticated", None)
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)
    session.pop("admin_role", None)

    flash("Administrator session terminated.", "info")
    return redirect(url_for("dashboard_ui.landing"))


@admin_bp.route("/dashboard")
@admin_required
def admin_dashboard():
    """Protected Admin Command Dashboard Overview."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    try:
        summary = dash_service.get_summary_stats()
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).warning(f"Error getting summary stats in admin_dashboard: {e}")
        summary = {}

    try:
        cat_dist = stats_service.get_category_distribution()
    except Exception:
        cat_dist = {}

    try:
        prio_dist = stats_service.get_priority_distribution()
    except Exception:
        prio_dist = {}

    try:
        src_dist = stats_service.get_source_distribution()
    except Exception:
        src_dist = {}

    try:
        daily_trends = stats_service.get_daily_opportunity_trends()
    except Exception:
        daily_trends = {"labels": [], "counts": []}

    try:
        audit_res = audit_repo.query_logs(limit=10)
        recent_audits = audit_res.get("logs", []) if isinstance(audit_res, dict) else []
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).warning(f"Error querying audit logs in admin_dashboard: {e}")
        recent_audits = []

    # Compile Phase B-G Staging and Free-Only Pipeline Metrics
    staging_summary = {
        "total_discovered": 0,
        "total_extracted": 0,
        "total_classified": 0,
        "total_approved": 0,
        "total_quarantined": 0,
        "total_rejected": 0,
        "newly_promoted": 0,
    }
    try:
        from src.discovery.promotion_repository import PromotionRepository
        import datetime
        today_str = datetime.date.today().isoformat()
        promo_repo = PromotionRepository(db_manager=admin_repo.db_manager)
        stg_meta = promo_repo.get_daily_summary_counts(report_date=today_str)
        staging_summary = {
            "total_discovered": getattr(stg_meta, "total_discovered", 0),
            "total_extracted": getattr(stg_meta, "total_extracted", 0),
            "total_classified": getattr(stg_meta, "total_classified", 0),
            "total_approved": getattr(stg_meta, "total_approved", 0),
            "total_quarantined": getattr(stg_meta, "total_quarantined", 0),
            "total_rejected": getattr(stg_meta, "total_rejected", 0),
            "newly_promoted": getattr(stg_meta, "newly_promoted_count", 0),
        }
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).debug(f"Could not load staging summary: {e}")

    safety_flags = {
        "promotion_enabled": os.getenv("PROMOTION_ENABLED", "false").lower() == "true",
        "promotion_dry_run": os.getenv("PROMOTION_DRY_RUN", "true").lower() == "true",
        "daily_report_enabled": os.getenv("DAILY_REPORT_ENABLED", "false").lower() == "true",
        "email_delivery_enabled": os.getenv("EMAIL_DELIVERY_ENABLED", "false").lower() == "true",
    }

    return render_template(
        "admin/admin_dashboard.html",
        active_page="admin_dashboard",
        summary=summary,
        category_distribution=cat_dist,
        priority_distribution=prio_dist,
        source_distribution=src_dist,
        daily_trends=daily_trends,
        recent_audits=recent_audits,
        staging_summary=staging_summary,
        safety_flags=safety_flags,
    )


@admin_bp.route("/collectors")
@admin_required
def admin_collectors():
    """Protected Collectors Overview & Controls."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    collectors_list = dash_service.get_collectors_status()
    return render_template(
        "admin/admin_collectors.html",
        active_page="admin_collectors",
        collectors=collectors_list,
    )


@admin_bp.route("/scheduler")
@admin_required
def admin_scheduler():
    """Protected Scheduler Management & Control Panel."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    sched_status = api_service.get_scheduler_status()
    return render_template(
        "admin/admin_scheduler.html",
        active_page="admin_scheduler",
        scheduler_status=sched_status,
    )


@admin_bp.route("/logs")
@admin_required
def admin_logs():
    """Protected App Logs & Audit Trail Control Center."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    level = request.args.get("level", "ALL")
    module = request.args.get("module", "ALL")
    search_q = request.args.get("q", "")
    page, limit = parse_pagination(request, default_page=1, default_limit=50, max_limit=200)
    tab = request.args.get("tab", "app_logs")

    app_logs_res = log_repo.query_logs(
        level=level,
        module=module,
        search_query=search_q,
        page=page,
        limit=limit,
    )
    audit_logs_res = audit_repo.query_logs(
        search_query=search_q,
        page=page,
        limit=limit,
    )
    stats = log_repo.get_log_stats()
    active_pagination = audit_logs_res if tab == "audit_logs" else app_logs_res

    return render_template(
        "admin/admin_logs.html",
        active_page="admin_logs",
        logs=app_logs_res.get("logs", []),
        audit_logs=audit_logs_res.get("logs", []),
        pagination=active_pagination,
        stats=stats,
        selected_level=level,
        selected_module=module,
        search_query=search_q,
        active_tab=tab,
        current_page=page,
        current_limit=limit,
    )


@admin_bp.route("/configuration")
@admin_required
def admin_configuration():
    """Protected YAML Configuration Editor."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    configs = {}
    for yaml_file in CONFIG_DIR.glob("*.yaml"):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                configs[yaml_file.name] = f.read()
        except Exception:
            configs[yaml_file.name] = "# Error reading file"

    return render_template(
        "admin/admin_configuration.html",
        active_page="admin_configuration",
        configs=configs,
    )


@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    """Protected User Management & Account Administration with full RBAC CRUD."""
    if request.method == "GET" and request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    tab = request.args.get("tab", "users")

    if request.method == "POST":
        csrf_token = request.form.get("csrf_token", "").strip() or request.headers.get("X-CSRF-Token", "").strip()
        expected_csrf = session.get("admin_csrf_token")
        if not expected_csrf or not AdminSecurityManager.verify_csrf_token(expected_csrf, csrf_token):
            flash("CSRF validation failed.", "danger")
            client_ip = get_client_ip(request)
            try:
                audit_repo.log_event("USER_MGMT", "CSRF_FAILURE", "FAILED", username=session.get("admin_username"), source_ip=client_ip, details="CSRF token validation failed")
            except Exception:
                pass
            users_list = user_repo.list_users()
            admins_list = admin_repo.get_all()
            return render_template(
                "admin/admin_users.html",
                active_page="admin_users",
                users=users_list,
                admins=admins_list,
                active_tab=tab,
            ), 403

        action = request.form.get("action")
        client_ip = get_client_ip(request)
        curr_admin_id = session.get("admin_user_id")

        if action == "create_user":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()
            role = request.form.get("role", "Operator").strip()

            is_admin_role = role in ("Super Admin", "Administrator", "Admin", "admin")

            if is_admin_role:
                valid, msg = AdminSecurityManager.validate_password_strength(password)
                if not valid:
                    flash(f"Administrator Password Policy Violation: {msg}", "danger")
                else:
                    try:
                        admin_repo.create_admin(username=username, email=email, password=password, role="Administrator")
                        audit_repo.log_event("USER_MGMT", "CREATE_ADMIN", "SUCCESS", username=session.get("admin_username"), source_ip=client_ip, details=f"Admin '{session.get('admin_username')}' provisioned administrator '{username}' into Admins table")
                        flash(f"Administrator '{username}' provisioned successfully.", "success")
                        tab = "admins"
                    except ValueError as e:
                        flash(str(e), "danger")
            else:
                if len(password) < 8:
                    flash("Standard user password must be at least 8 characters long.", "danger")
                else:
                    clean_role = role if role in ("Viewer", "Operator", "User") else "Viewer"
                    try:
                        user_repo.create_user(username=username, email=email, password=password, role=clean_role)
                        audit_repo.log_event("USER_MGMT", "CREATE_USER", "SUCCESS", username=session.get("admin_username"), source_ip=client_ip, details=f"Admin '{session.get('admin_username')}' created user '{username}' with role '{clean_role}' in Users table")
                        flash(f"User '{username}' created successfully as {clean_role}.", "success")
                        tab = "users"
                    except ValueError as e:
                        flash(str(e), "danger")

        elif action == "toggle_status":
            target_type = request.form.get("target_type", "user")
            account_id = request.form.get("account_id")

            if target_type == "admin":
                tab = "admins"
                try:
                    admin_int_id = int(account_id)
                    if admin_int_id == curr_admin_id:
                        flash("You cannot lock or deactivate your own administrative account while active.", "warning")
                    else:
                        new_state = admin_repo.toggle_admin_status(admin_int_id)
                        state_label = "activated" if new_state else "locked"
                        audit_repo.log_event("USER_MGMT", "TOGGLE_ADMIN_STATUS", "SUCCESS", username=session.get("admin_username"), source_ip=client_ip, details=f"Admin {account_id} status changed to {state_label}")
                        flash(f"Administrator #{account_id} {state_label} successfully.", "success")
                except Exception as e:
                    flash(f"Failed to update administrator status: {e}", "danger")
            else:
                tab = "users"
                try:
                    new_state = user_repo.toggle_user_status(account_id)
                    state_label = "activated" if new_state else "locked"
                    audit_repo.log_event("USER_MGMT", "TOGGLE_USER_STATUS", "SUCCESS", username=session.get("admin_username"), source_ip=client_ip, details=f"User {account_id} status changed to {state_label}")
                    flash(f"User #{account_id[:8]}... {state_label} successfully.", "success")
                except Exception as e:
                    flash(f"Failed to update user status: {e}", "danger")

        elif action == "delete_account":
            target_type = request.form.get("target_type", "user")
            account_id = request.form.get("account_id")

            if target_type == "admin":
                tab = "admins"
                try:
                    admin_int_id = int(account_id)
                    if admin_int_id == curr_admin_id:
                        flash("You cannot delete your own administrative account while active.", "danger")
                    else:
                        deleted = admin_repo.delete_admin(admin_int_id)
                        if deleted:
                            audit_repo.log_event("USER_MGMT", "DELETE_ADMIN", "SUCCESS", username=session.get("admin_username"), source_ip=client_ip, details=f"Admin {account_id} deleted permanently")
                            flash(f"Administrator #{account_id} deleted successfully.", "success")
                        else:
                            flash("Administrator account not found.", "warning")
                except Exception as e:
                    flash(f"Failed to delete administrator: {e}", "danger")
            else:
                tab = "users"
                try:
                    deleted = user_repo.delete_user(account_id)
                    if deleted:
                        audit_repo.log_event("USER_MGMT", "DELETE_USER", "SUCCESS", username=session.get("admin_username"), source_ip=client_ip, details=f"User {account_id} deleted permanently")
                        flash("User account deleted successfully.", "success")
                    else:
                        flash("User account not found.", "warning")
                except Exception as e:
                    flash(f"Failed to delete user: {e}", "danger")

    users_list = user_repo.list_users()
    admins_list = admin_repo.get_all()
    return render_template(
        "admin/admin_users.html",
        active_page="admin_users",
        users=users_list,
        admins=admins_list,
        active_tab=tab,
    )



@admin_bp.route("/reports")
@admin_required
def admin_reports():
    """Protected Reports Center."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    reports = api_service.get_reports_list()
    return render_template(
        "admin/admin_reports.html",
        active_page="admin_reports",
        reports=reports,
    )


@admin_bp.route("/reports/download/<path:filename>")
@admin_required
def admin_download_report(filename):
    """Protected report download."""
    reports_dir = REPORTS_DIR
    if not reports_dir.exists():
        abort(404)
    audit_repo.log_event("REPORTS", "DOWNLOAD_REPORT", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Admin '{session.get('admin_username')}' downloaded report '{filename}'")
    return send_from_directory(str(reports_dir), filename, as_attachment=True)


@admin_bp.route("/diagnostics")
@admin_required
def admin_diagnostics():
    """Protected System & Feed Diagnostics Control."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    diag_summary = RSSDiagnosticsManager().get_feed_diagnostics_summary()
    audit_repo.log_event("DIAGNOSTICS", "ACCESS_DIAGNOSTICS", "SUCCESS", username=session.get("admin_username"), source_ip=get_client_ip(request), details=f"Admin '{session.get('admin_username')}' viewed feed diagnostics")
    return render_template(
        "admin/admin_diagnostics.html",
        active_page="admin_diagnostics",
        diag=diag_summary,
    )


@admin_bp.route("/system")
@admin_required
def admin_system():
    """Protected System Specifications & Metadata."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    version_info = get_version_info()
    sys_specs = {
        "app_name": version_info.get("app_name", "CyberScout AI"),
        "version": version_info.get("version", "2.2.0"),
        "build_date": version_info.get("build_date", "2026-08-06"),
        "python_version": version_info.get("python_version", "3.12.10"),
        "platform": version_info.get("platform", "Windows-11"),
        "git_tag": "v2.2-admin-hardening",
        "uptime": "Active",
    }
    return render_template(
        "admin/admin_system.html",
        active_page="admin_system",
        sys_specs=sys_specs,
    )


@admin_bp.route("/email")
@admin_required
def admin_email():
    """Protected Email Provider Diagnostics & Notification Outbox Observability."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    res = api_service.check_smtp_health()
    outbox_stats = {}
    try:
        from src.database.notification_repository import NotificationRepository
        outbox_stats = NotificationRepository(db_manager=admin_repo.db_manager).get_admin_observability_stats()
    except Exception as nre:
        from src.core.logging import get_logger
        get_logger(__name__).warning(f"Could not load notification outbox stats: {nre}")

    return render_template(
        "admin/admin_email.html",
        active_page="admin_email",
        smtp_health=res,
        outbox_stats=outbox_stats,
    )


@admin_bp.route("/profile", methods=["GET", "POST"])
@admin_required
def admin_profile():
    """
    Dedicated Administrator Profile View and Account Settings Management.
    Accessible ONLY to authenticated administrators via @admin_required.
    Queries the 'Admins' table exclusively.
    """
    client_ip = get_client_ip(request)
    admin_id = session.get("admin_user_id")
    admin_username = session.get("admin_username")

    # Fetch admin data exclusively from Admins table
    admin_record = None
    if admin_id:
        try:
            admin_record = admin_repo.get_by_id(int(admin_id))
        except Exception as e:
            from src.core.logging import get_logger
            get_logger(__name__).error(f"Error fetching admin profile by id {admin_id}: {e}")

    if not admin_record and admin_username:
        try:
            admin_record = admin_repo.get_by_username(str(admin_username))
        except Exception as e:
            from src.core.logging import get_logger
            get_logger(__name__).error(f"Error fetching admin profile by username {admin_username}: {e}")

    if not admin_record and session.get("admin_email"):
        try:
            admin_record = admin_repo.get_by_email(str(session.get("admin_email")))
        except Exception as e:
            from src.core.logging import get_logger
            get_logger(__name__).error(f"Error fetching admin profile by email: {e}")

    if not admin_record or admin_record.get("id") is None:
        flash("Could not retrieve administrator profile details. Please log in again.", "danger")
        return redirect(url_for("admin_ui.admin_login"))

    resolved_admin_id = int(admin_record["id"])
    resolved_username = str(admin_record.get("username") or admin_username or "Administrator")
    resolved_email = str(admin_record.get("email") or "")
    is_active = bool(admin_record.get("is_active", True))
    created_at = admin_record.get("created_at")
    last_login = admin_record.get("last_login")

    pending_token = session.get("admin_pending_pw_token")
    pending_state = AdminSecurityManager.get_pending_password_change(pending_token) if pending_token else None

    # Auto-prune expired pending state on GET
    if pending_state and (int(time.time()) > pending_state.get("expires_at", 0) or pending_state.get("account_id") != resolved_admin_id):
        AdminSecurityManager.clear_pending_password_change(pending_token)
        session.pop("admin_pending_pw_token", None)
        pending_state = None

    if request.method == "POST":
        csrf_token = request.form.get("csrf_token", "").strip()
        if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
            audit_repo.log_event(
                "AUTH",
                "ADMIN_PASSWORD_CHANGE",
                "CSRF_FAILED",
                user_id=None,
                username=resolved_username,
                source_ip=client_ip,
                details="CSRF token validation failed on admin password change",
            )
            flash("CSRF validation failed. Please try again.", "danger")
            return redirect(url_for("admin_ui.admin_profile"))

        action = request.form.get("action", "request_pw_change")

        # Action 1: Cancel Pending OTP
        if action == "cancel_pw_otp":
            if pending_token:
                AdminSecurityManager.clear_pending_password_change(pending_token)
                session.pop("admin_pending_pw_token", None)
            flash("Password change cancelled.", "info")
            return redirect(url_for("admin_ui.admin_profile"))

        # Action 2: Resend OTP Code
        elif action == "resend_pw_otp":
            if not pending_token or not pending_state or pending_state.get("target_type") != "admin" or pending_state.get("account_id") != resolved_admin_id:
                flash("No active password change request found. Please initiate a new request.", "warning")
                session.pop("admin_pending_pw_token", None)
                return redirect(url_for("admin_ui.admin_profile"))

            # Enforce 30-second resend cooldown
            now = int(time.time())
            last_resend = pending_state.get("last_resend_at", 0)
            if now - last_resend < 30:
                wait_sec = 30 - (now - last_resend)
                flash(f"Please wait {wait_sec} seconds before requesting a new code.", "warning")
                return redirect(url_for("admin_ui.admin_profile"))

            new_otp = AdminSecurityManager.generate_otp_code()
            new_otp_hash = AdminSecurityManager.hash_otp_code(new_otp)
            new_expires_at = now + 300
            AdminSecurityManager.update_pending_password_change_otp(str(pending_token), new_otp_hash, new_expires_at)

            try:
                from src.notifier.email_sender import EmailSender
                sender = EmailSender()
                subject = "CyberScout AI — Administrator Password Change Verification Code"
                plain_body = f"Hello {resolved_username},\n\nYour new 6-digit administrator verification code is:\n\n   {new_otp}\n\nThis code is valid for 5 minutes. Do not share this code.\n\nCyberScout AI Security"
                html_body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif; background-color:#0f172a; color:#f8fafc; padding:30px;">
                <div style="max-width:500px; margin:0 auto; background-color:#1e293b; padding:30px; border-radius:10px; border:1px solid #334155;">
                  <h2 style="color:#ef4444; margin-top:0;">CyberScout AI Security</h2>
                  <p>Administrator Password Change Verification Code:</p>
                  <div style="background-color:#0f172a; border:1px solid #ef4444; color:#ef4444; font-size:32px; font-weight:bold; letter-spacing:5px; text-align:center; padding:15px; border-radius:8px; margin:20px 0;">
                    {new_otp}
                  </div>
                  <p style="font-size:13px; color:#94a3b8;">This code is valid for 5 minutes. If you did not request this change, please notify system administrators immediately.</p>
                </div>
                </body></html>"""
                msg_id = sender.send_email(
                    html_content=html_body,
                    plain_content=plain_body,
                    subject=subject,
                    recipient=resolved_email or os.getenv("EMAIL_TO") or "admin@cyberscout.ai",
                )
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_REQUESTED",
                    "SUCCESS",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details=f"Admin password change OTP resent to {AdminSecurityManager.mask_email(resolved_email)} (msg_id={msg_id})",
                )
                flash("A new verification code has been dispatched to your registered email.", "info")
            except Exception as e:
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_REQUESTED",
                    "DISPATCH_FAILED",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details=f"Failed to resend admin password change OTP: {e}",
                )
                flash("Could not send verification code. Please try again.", "danger")
            return redirect(url_for("admin_ui.admin_profile"))

        # Action 3: Verify OTP Code and Finalize Password Update
        elif action == "verify_pw_otp":
            if not pending_token or not pending_state or pending_state.get("target_type") != "admin" or pending_state.get("account_id") != resolved_admin_id:
                flash("No active password change request found or session expired. Please start again.", "warning")
                session.pop("admin_pending_pw_token", None)
                return redirect(url_for("admin_ui.admin_profile"))

            # Check expiration
            if int(time.time()) > pending_state.get("expires_at", 0):
                AdminSecurityManager.clear_pending_password_change(str(pending_token))
                session.pop("admin_pending_pw_token", None)
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_FAILED",
                    "EXPIRED",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details="Admin password change OTP expired",
                )
                flash("Verification code has expired. Please initiate the password change again.", "danger")
                return redirect(url_for("admin_ui.admin_profile"))

            # Increment and check attempt limit (max 5 attempts)
            attempts = AdminSecurityManager.increment_pending_password_change_attempts(str(pending_token))
            if attempts > 5:
                AdminSecurityManager.clear_pending_password_change(pending_token)
                session.pop("admin_pending_pw_token", None)
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_FAILED",
                    "MAX_ATTEMPTS_EXCEEDED",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details="Exceeded maximum OTP attempts for password change",
                )
                flash("Maximum verification attempts exceeded. Please request a new password change.", "danger")
                return redirect(url_for("admin_ui.admin_profile"))

            otp_input = request.form.get("otp_code", "").strip()
            if not AdminSecurityManager.verify_otp_code(otp_input, pending_state["otp_hash"]):
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_FAILED",
                    "INVALID_CODE",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details=f"Invalid OTP entered for admin password change (attempt {attempts}/5)",
                )
                flash(f"Invalid verification code. {max(0, 5 - attempts)} attempts remaining.", "danger")
                return redirect(url_for("admin_ui.admin_profile"))

            # OTP Verified Successfully!
            new_password_hash = pending_state["new_password_hash"]
            try:
                admin_repo.update_password_hash(resolved_admin_id, new_password_hash)
                AdminSecurityManager.clear_pending_password_change(pending_token)
                session.pop("admin_pending_pw_token", None)

                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_VERIFIED",
                    "SUCCESS",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details="Admin password change OTP verified successfully",
                )
                audit_repo.log_event(
                    "AUTH",
                    "ADMIN_PASSWORD_CHANGE",
                    "SUCCESS",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details=f"Admin '{resolved_username}' password updated successfully after OTP verification",
                )
                flash("Administrator password updated successfully.", "success")
                return redirect(url_for("admin_ui.admin_profile"))
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).error(f"Error updating admin password hash: {e}")
                audit_repo.log_event(
                    "AUTH",
                    "ADMIN_PASSWORD_CHANGE",
                    "FAILED",
                    user_id=None,
                    username=resolved_username,
                    source_ip=client_ip,
                    details=f"Database error during admin password update: {e}",
                )
                flash("Failed to update password. Please try again.", "danger")
                return redirect(url_for("admin_ui.admin_profile"))

        # Action 4 (Default): Validate Password Form & Initiate OTP Verification
        else:
            current_pw = request.form.get("current_password", "").strip()
            new_pw = request.form.get("new_password", "").strip()
            confirm_pw = request.form.get("confirm_password", "").strip()

            if not current_pw or not new_pw or not confirm_pw:
                flash("All password fields are required.", "warning")
            elif new_pw != confirm_pw:
                flash("New password and confirmation do not match.", "danger")
            elif current_pw == new_pw:
                flash("New password cannot be identical to your current password.", "warning")
            else:
                # Validate admin password strength (min 10 chars, uppercase, lowercase, digit, special char)
                valid, strength_msg = AdminSecurityManager.validate_password_strength(new_pw)
                if not valid:
                    flash(f"Password requirement not met: {strength_msg}", "danger")
                elif not admin_repo.verify_password(resolved_admin_id, current_pw):
                    audit_repo.log_event(
                        "AUTH",
                        "ADMIN_PASSWORD_CHANGE",
                        "INVALID_CURRENT_PW",
                        user_id=None,
                        username=resolved_username,
                        source_ip=client_ip,
                        details="Incorrect current password provided for admin account",
                    )
                    flash("Current password is incorrect.", "danger")
                else:
                    # Validated! Generate OTP and create pending transaction
                    from werkzeug.security import generate_password_hash
                    pw_hash = generate_password_hash(new_pw, method="pbkdf2:sha256")
                    otp_code = AdminSecurityManager.generate_otp_code()
                    otp_hash = AdminSecurityManager.hash_otp_code(otp_code)
                    expires_at = int(time.time()) + 300  # 5 minutes

                    new_pending_token = AdminSecurityManager.store_pending_password_change(
                        target_type="admin",
                        account_id=resolved_admin_id,
                        username=resolved_username,
                        email=resolved_email,
                        new_password_hash=pw_hash,
                        otp_hash=otp_hash,
                        expires_at=expires_at,
                    )
                    session["admin_pending_pw_token"] = new_pending_token

                    # Transmit OTP Code via Production Email Service
                    try:
                        from src.notifier.email_sender import EmailSender
                        sender = EmailSender()
                        subject = "CyberScout AI — Administrator Password Change Verification Code"
                        plain_body = f"Hello {resolved_username},\n\nYour 6-digit administrator verification code is:\n\n   {otp_code}\n\nThis code is valid for 5 minutes. Do not share this code with anyone.\n\nCyberScout AI Security"
                        html_body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif; background-color:#0f172a; color:#f8fafc; padding:30px;">
                        <div style="max-width:500px; margin:0 auto; background-color:#1e293b; padding:30px; border-radius:10px; border:1px solid #334155;">
                          <h2 style="color:#ef4444; margin-top:0;">CyberScout AI Security</h2>
                          <p>Administrator Password Change Verification Code:</p>
                          <div style="background-color:#0f172a; border:1px solid #ef4444; color:#ef4444; font-size:32px; font-weight:bold; letter-spacing:5px; text-align:center; padding:15px; border-radius:8px; margin:20px 0;">
                            {otp_code}
                          </div>
                          <p style="font-size:13px; color:#94a3b8;">This code is valid for 5 minutes. If you did not request this change, please inspect audit logs immediately.</p>
                        </div>
                        </body></html>"""

                        dest_email = resolved_email or os.getenv("EMAIL_TO") or "admin@cyberscout.ai"
                        msg_id = sender.send_email(
                            html_content=html_body,
                            plain_content=plain_body,
                            subject=subject,
                            recipient=dest_email,
                        )
                        audit_repo.log_event(
                            "AUTH",
                            "PASSWORD_CHANGE_OTP_REQUESTED",
                            "SUCCESS",
                            user_id=None,
                            username=resolved_username,
                            source_ip=client_ip,
                            details=f"Admin password change OTP dispatched to {AdminSecurityManager.mask_email(dest_email)} (msg_id={msg_id})",
                        )
                        flash("A 6-digit verification code has been sent to your registered email address.", "info")
                    except Exception as e:
                        AdminSecurityManager.clear_pending_password_change(new_pending_token)
                        session.pop("admin_pending_pw_token", None)
                        from src.core.logging import get_logger
                        get_logger(__name__).error(f"Failed to dispatch admin password change OTP: {e}")
                        audit_repo.log_event(
                            "AUTH",
                            "PASSWORD_CHANGE_OTP_REQUESTED",
                            "DISPATCH_FAILED",
                            user_id=None,
                            username=resolved_username,
                            source_ip=client_ip,
                            details=f"Failed to dispatch password change OTP email: {e}",
                        )
                        flash("Could not send verification code. Please try again.", "danger")
                    return redirect(url_for("admin_ui.admin_profile"))

    # Log profile view (on GET)
    if request.method == "GET":
        try:
            audit_repo.log_event(
                "AUTH",
                "ADMIN_PROFILE_VIEW",
                "SUCCESS",
                user_id=None,
                username=resolved_username,
                source_ip=client_ip,
                details=f"Admin '{resolved_username}' viewed profile",
            )
        except Exception:
            pass

    admin_info = {
        "username": resolved_username,
        "email": resolved_email,
        "is_active": is_active,
        "created_at": created_at,
        "last_login": last_login,
        "role": "Administrator Account",
    }

    return render_template(
        "admin/admin_profile.html",
        active_page="admin_profile",
        csrf_token=session.get("admin_csrf_token", ""),
        admin_info=admin_info,
        pending_otp=bool(pending_state),
        masked_email=AdminSecurityManager.mask_email(pending_state.get("email") or resolved_email) if pending_state else "",
    )


@admin_bp.route("/source-health", methods=["GET"])
@admin_required
def admin_source_health():
    """Admin-only Source Health Dashboard view displaying per-source status and metrics."""
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    from src.database.source_health_repository import SourceHealthRepository
    health_repo = SourceHealthRepository()
    records = health_repo.get_all_health_records()

    total_sources = len(records)
    healthy_count = sum(1 for r in records if (r.health_status.value if hasattr(r.health_status, "value") else r.health_status).upper() == "HEALTHY")
    degraded_count = sum(1 for r in records if (r.health_status.value if hasattr(r.health_status, "value") else r.health_status).upper() in {"DEGRADED", "STALE"})
    failed_count = sum(1 for r in records if (r.health_status.value if hasattr(r.health_status, "value") else r.health_status).upper() == "FAILED")

    return render_template(
        "admin/admin_source_health.html",
        active_page="admin_source_health",
        records=records,
        total_sources=total_sources,
        healthy_count=healthy_count,
        degraded_count=degraded_count,
        failed_count=failed_count,
        csrf_token=session.get("admin_csrf_token", ""),
    )


@admin_bp.route("/data-quality", methods=["GET", "POST"])
@admin_required
def admin_data_quality():
    """Admin-only Data Quality Dashboard view displaying lifecycle counts, quarantine records, completeness metrics."""
    if request.method == "POST":
        return admin_quarantine_action()

    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    from src.database.connection import DatabaseManager
    db = DatabaseManager()

    metrics: dict = {
        "total": 0,
        "active": 0,
        "closing_soon": 0,
        "expired": 0,
        "stale": 0,
        "quarantined": 0,
        "removed": 0,
        "missing_critical": 0,
    }
    quarantined_samples: list = []

    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        # 1. Total opportunities
        cursor.execute('SELECT COUNT(*) FROM "Opportunities";')
        row = cursor.fetchone()
        metrics["total"] = int(row[0] if row else 0)

        # 2. Counts by lifecycle_status
        cursor.execute('SELECT COALESCE(lifecycle_status, status, \'active\'), COUNT(*) FROM "Opportunities" GROUP BY 1;')
        for r in cursor.fetchall():
            status_name = str(r[0]).lower()
            cnt = int(r[1])
            if status_name in metrics:
                metrics[status_name] += cnt

        # 3. Quarantined count (Opportunities + DiscoveredCandidates)
        cursor.execute('SELECT COUNT(*) FROM "Opportunities" WHERE quality_status = \'quarantined\' OR status = \'quarantined\';')
        row = cursor.fetchone()
        opp_quarantined = int(row[0] if row else 0)

        cand_quarantined = 0
        try:
            cursor.execute('SELECT COUNT(*) FROM "DiscoveredCandidates" WHERE free_only_decision = \'QUARANTINED\';')
            crow = cursor.fetchone()
            cand_quarantined = int(crow[0] if crow else 0)
        except Exception:
            pass

        metrics["quarantined"] = opp_quarantined + cand_quarantined

        # 4. Missing critical fields
        cursor.execute('SELECT COUNT(*) FROM "Opportunities" WHERE title IS NULL OR title = \'\' OR url IS NULL OR url = \'\';')
        row = cursor.fetchone()
        metrics["missing_critical"] = int(row[0] if row else 0)

        # 5. Fetch recent quarantined records from Opportunities
        cursor.execute(
            'SELECT id, title, source_id, quarantine_reason, discovered_date, completeness_score '
            'FROM "Opportunities" WHERE quality_status = \'quarantined\' '
            'ORDER BY discovered_date DESC LIMIT 30;'
        )
        for r in cursor.fetchall():
            quarantined_samples.append({
                "id": r[0],
                "title": r[1] or "Untitled",
                "source_id": r[2] or "unknown",
                "quarantine_reason": r[3] or "Validation failure",
                "discovered_date": str(r[4] or "")[:10],
                "completeness_score": round(float(r[5] or 0.0), 2),
                "type": "Production Opportunity",
            })

        # 6. Fetch staged quarantined records from DiscoveredCandidates
        try:
            cursor.execute(
                'SELECT id, title, source_domain, verification_reason, discovered_at, category '
                'FROM "DiscoveredCandidates" WHERE free_only_decision = \'QUARANTINED\' '
                'ORDER BY discovered_at DESC LIMIT 30;'
            )
            for r in cursor.fetchall():
                quarantined_samples.append({
                    "id": r[0],
                    "title": r[1] or "Untitled Candidate",
                    "source_id": r[2] or "Tavily Discovery",
                    "quarantine_reason": r[3] or "Pricing ambiguity / Free-Only quarantine",
                    "discovered_date": str(r[4] or "")[:10],
                    "completeness_score": 0.85,
                    "type": "Staged Candidate",
                })
        except Exception:
            pass

        cursor.close()
        conn.close()
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Error compiling admin data quality metrics: {e}")

    return render_template(
        "admin/admin_data_quality.html",
        active_page="admin_data_quality",
        metrics=metrics,
        quarantined_records=quarantined_samples,
        csrf_token=session.get("admin_csrf_token", ""),
    )


@admin_bp.route("/quarantine/action", methods=["POST"])
@admin_required
def admin_quarantine_action():
    """Admin-only action to approve or reject/archive quarantined records with CSRF and audit logging."""
    client_ip = get_client_ip(request)
    resolved_username = session.get("admin_username") or "admin"
    json_payload = request.get_json(silent=True)
    is_json = (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    payload = json_payload if isinstance(json_payload, dict) else {}
    raw_csrf_token = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or payload.get("csrf_token")
        or request.form.get("csrf_token", "")
    )
    csrf_token = raw_csrf_token.strip() if isinstance(raw_csrf_token, str) else ""

    if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
        if is_json:
            return jsonify({"status": "failed", "error": "CSRF validation failed."}), 403
        flash("CSRF validation failed.", "danger")
        return redirect(url_for("admin_ui.admin_data_quality"))

    action_value = payload.get("action", request.form.get("action", ""))
    id_value = payload.get("opportunity_id") or payload.get("item_id") or request.form.get("opportunity_id") or request.form.get("item_id", "")
    record_type_value = payload.get("record_type") or payload.get("type") or request.form.get("record_type", "")
    action = action_value.strip().lower() if isinstance(action_value, str) else ""
    opportunity_id = id_value.strip() if isinstance(id_value, str) else ""
    record_type = record_type_value.strip() if isinstance(record_type_value, str) else ""

    if (
        not opportunity_id
        or action not in {"approve", "reject"}
        or record_type not in {"", "Production Opportunity", "Staged Candidate"}
    ):
        if is_json:
            return jsonify({"status": "failed", "error": "Invalid quarantine action parameters."}), 400
        flash("Invalid quarantine action parameters.", "danger")
        return redirect(url_for("admin_ui.admin_data_quality"))

    from src.database.connection import DatabaseManager
    db = DatabaseManager()
    try:
        updated_count = 0
        with db.transaction() as cursor:
            if record_type != "Staged Candidate":
                if action == "approve":
                    cursor.execute(
                        'UPDATE "Opportunities" SET quality_status = \'passed\', is_rejected = FALSE, quarantine_reason = NULL '
                        'WHERE id = %s AND (quality_status = \'quarantined\' OR status = \'quarantined\');',
                        (opportunity_id,)
                    )
                else:
                    cursor.execute(
                        'UPDATE "Opportunities" SET quality_status = \'rejected\', is_rejected = TRUE, lifecycle_status = \'removed\', status = \'archived\' '
                        'WHERE id = %s AND (quality_status = \'quarantined\' OR status = \'quarantined\');',
                        (opportunity_id,)
                    )
                updated_count += max(cursor.rowcount, 0)

            if record_type != "Production Opportunity":
                cursor.execute('SELECT to_regclass(%s);', ('public."DiscoveredCandidates"',))
                if cursor.fetchone():
                    candidate_decision = "APPROVED" if action == "approve" else "REJECTED"
                    cursor.execute(
                        'UPDATE "DiscoveredCandidates" SET free_only_decision = %s '
                        'WHERE id = %s AND free_only_decision = \'QUARANTINED\';',
                        (candidate_decision, opportunity_id)
                    )
                    updated_count += max(cursor.rowcount, 0)
        if not updated_count:
            if is_json:
                return jsonify({"status": "failed", "error": "Record not found or already reviewed."}), 404
            flash("Record not found or already reviewed.", "warning")
            return redirect(url_for("admin_ui.admin_data_quality"))

        audit_repo.log_event(
            "DATA_QUALITY",
            f"QUARANTINE_{action.upper()}",
            "SUCCESS",
            username=resolved_username,
            source_ip=client_ip,
            details=f"Admin {resolved_username} performed '{action}' on opportunity {opportunity_id}",
        )
        if is_json:
            return jsonify({"status": "success", "action": action})
        flash(f"Quarantined record successfully updated ({action}).", "success")
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Failed to execute quarantine action: {e}")
        if is_json:
            return jsonify({"status": "failed", "error": "Failed to update the quarantined record."}), 500
        flash("Failed to execute quarantine action.", "danger")

    return redirect(url_for("admin_ui.admin_data_quality"))


@admin_bp.route("/analytics", methods=["GET"])
@admin_required
def admin_analytics():
    """
    Dedicated Administrative Operational Analytics Dashboard (Phase 8).
    Displays platform-wide volume, source health, lifecycle & quality distributions,
    quarantine breakdown, and Phase 7 notification delivery rates.
    """
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    analytics_svc = AnalyticsService()
    admin_data = analytics_svc.get_admin_analytics()

    return render_template(
        "admin/admin_analytics.html",
        active_page="admin_analytics",
        admin_data=admin_data,
        overview=admin_data.platform_overview,
        sources=admin_data.source_health_summary,
        lifecycle=admin_data.lifecycle_distribution,
        quality=admin_data.quality_distribution,
        quarantine=admin_data.quarantine_summary,
        notifications=admin_data.notification_metrics,
        trends=admin_data.recent_trends,
    )


@admin_bp.route("/reliability", methods=["GET"])
@admin_required
def admin_reliability():
    """
    Dedicated Administrative Reliability, Observability & Disaster Recovery Dashboard (Phase 10).
    Displays liveness/readiness telemetry, connection pool health, scan job state & recovery,
    notification outbox status, and local database backup verification status.
    """
    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

    from src.database.connection import DatabaseManager
    from src.maintenance.backup_manager import BackupManager
    from src.database.scan_job_repository import ScanJobRepository
    from src.database.notification_repository import NotificationRepository
    from src.database.source_health_repository import SourceHealthRepository

    db = DatabaseManager()
    db_metrics = db.get_health_metrics()

    scan_repo = ScanJobRepository(db_manager=db)
    active_job = scan_repo.get_active_job()
    recent_jobs = scan_repo.list_recent_jobs(limit=10)

    backup_mgr = BackupManager(db_manager=db)
    backups = backup_mgr.list_backups()

    notif_repo = NotificationRepository(db_manager=db)
    outbox_stats = {}
    try:
        with db.transaction() as cur:
            cur.execute("""
                SELECT status, COUNT(*) 
                FROM "NotificationOutbox"
                GROUP BY status;
            """)
            outbox_stats = {r[0]: r[1] for r in cur.fetchall()}
    except Exception:
        outbox_stats = {}

    src_health_repo = SourceHealthRepository(db_manager=db)
    all_health = src_health_repo.get_all_health_records()
    healthy_sources = sum(1 for h in all_health if str(getattr(h, "health_status", "")).upper() == "HEALTHY")
    degraded_sources = len(all_health) - healthy_sources

    return render_template(
        "admin/admin_reliability.html",
        active_page="admin_reliability",
        db_metrics=db_metrics,
        active_job=active_job,
        recent_jobs=recent_jobs,
        backups=backups,
        outbox_stats=outbox_stats,
        total_sources=len(all_health),
        healthy_sources=healthy_sources,
        degraded_sources=degraded_sources,
    )

