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


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """
    Dedicated Admin Login Portal.
    Only allows users with role  'Administrator' to authenticate.
    """
    try:
        # If already authenticated as admin, redirect to admin dashboard
        if session.get("admin_authenticated"):
            return redirect(url_for("admin_ui.admin_dashboard"))

        client_ip = get_client_ip(request)

        if request.method == "POST":
            identifier = (
                request.form.get("admin_username", "").strip()
                or request.form.get("identifier", "").strip()
                or request.form.get("username", "").strip()
            )
            password = (
                request.form.get("admin_password", "").strip()
                or request.form.get("password", "").strip()
            )
            csrf_token = request.form.get("csrf_token", "").strip()
            next_url = request.form.get("next") or request.args.get("next") or url_for("admin_ui.admin_dashboard")

            # 1. Validate CSRF Token
            if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
                flash("CSRF validation failed. Please try again.", "danger")
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN", "FAILED", username=identifier, source_ip=client_ip, details="CSRF token mismatch")
                except Exception:
                    pass
                return render_template("admin/admin_login.html", next=next_url)

            # 2. Check Rate Limit / Account Lockout
            try:
                locked = AdminSecurityManager.is_locked_out(client_ip, identifier)
            except Exception:
                locked = False

            if locked:
                flash("Account locked due to 5 consecutive failed login attempts. Please wait 15 minutes.", "danger")
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN", "LOCKED_OUT", username=identifier, source_ip=client_ip, details="Attempt during lockout period")
                except Exception:
                    pass
                return render_template("admin/admin_login.html", next=next_url)

            # 3. Authenticate Administrator against Admins table
            try:
                user = admin_repo.authenticate(identifier, password)
                if not user:
                    legacy_user = user_repo.authenticate(identifier, password)
                    if legacy_user and str(legacy_user.get("role")).lower() in ("admin", "super admin", "administrator"):
                        user = legacy_user
            except Exception as e:
                from src.core.logging import get_logger
                get_logger(__name__).error(f"Administrator authentication error: {e}")
                user = None

            if not user:
                try:
                    AdminSecurityManager.record_failed_attempt(client_ip, identifier)
                except Exception:
                    pass
                flash("Invalid administrator credentials.", "danger")
                try:
                    audit_repo.log_event("AUTH", "ADMIN_LOGIN", "FAILED", username=identifier, source_ip=client_ip, details="Invalid credentials")
                except Exception:
                    pass
                return render_template("admin/admin_login.html", next=next_url)

            # 4. Role Authorization Check: Admin role permitted
            user_role = user.get("role") or user.get("account_type") or "Admin"
            if str(user_role).lower() not in ("admin", "super admin", "administrator"):
                try:
                    AdminSecurityManager.record_failed_attempt(client_ip, identifier)
                except Exception:
                    pass
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

            pending_token = AdminSecurityManager.store_pending_mfa(
                user_id=user["id"],
                username=user["username"],
                email=user["email"],
                role=user.get("role") or "Admin",
                otp_hash=otp_hash,
                expires_at=expires_at,
                next_url=next_url,
            )
            session["admin_pending_token"] = pending_token

            # Transmit OTP Code via Production Email Service
            try:
                from src.notifier.email_sender import EmailSender
                sender = EmailSender()
                subject = "CyberScout AI — Administrator Verification Code"
                plain_body = f"Hello {user['username']},\n\nYour 6-digit administrator verification code is:\n\n   {otp_code}\n\nThis code is valid for 5 minutes. Do not share this code with anyone.\n\nCyberScout AI Security"
                html_body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif; background-color:#0f172a; color:#f8fafc; padding:30px;">
                <div style="max-width:500px; margin:0 auto; background-color:#1e293b; padding:30px; border-radius:10px; border:1px solid #334155;">
                  <h2 style="color:#ef4444; margin-top:0;">CyberScout AI Security</h2>
                  <p>Administrator Multi-Factor Authentication Code:</p>
                  <div style="background-color:#0f172a; border:1px solid #ef4444; color:#ef4444; font-size:32px; font-weight:bold; letter-spacing:5px; text-align:center; padding:15px; border-radius:8px; margin:20px 0;">
                    {otp_code}
                  </div>
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
                flash("We couldn't send the verification code. Please try again or contact the administrator.", "danger")
                return render_template("admin/admin_login.html", next=next_url)

        return render_template("admin/admin_login.html", next=request.args.get("next", ""))
    except Exception as e:
        from src.core.logging import get_logger
        get_logger(__name__).error(f"Error rendering admin_login page: {e}")
        return render_template("admin/admin_login.html", next=request.args.get("next", ""))


@admin_bp.route("/verify-otp", methods=["GET", "POST"])
def admin_verify_otp():
    """
    Administrator OTP Verification (MFA) endpoint (Phases 6 - 8).
    Requires 6-digit numeric OTP code sent to admin's email.
    """
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_ui.admin_dashboard"))

    pending_token = session.get("admin_pending_token")
    mfa_state = AdminSecurityManager.get_pending_mfa(pending_token)

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
        audit_repo.log_event("MFA", "OTP_EXPIRED", "FAILED", username=username, source_ip=client_ip, details=f"OTP code expired for admin '{username}'")
        flash("Verification code has expired (valid for 5 minutes). Please log in again.", "danger")
        return redirect(url_for("admin_ui.admin_login"))

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        csrf_token = request.form.get("csrf_token", "").strip()

        if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
            flash("CSRF validation failed.", "danger")
            return render_template("admin/admin_verify_otp.html", username=username)

        # Track verification attempts
        attempts = AdminSecurityManager.increment_pending_mfa_attempts(pending_token_str)

        if attempts > 5:
            AdminSecurityManager.clear_pending_mfa(pending_token_str)
            session.pop("admin_pending_token", None)
            AdminSecurityManager.record_failed_attempt(client_ip, username)
            audit_repo.log_event("MFA", "OTP_LOCKOUT", "FAILED", username=username, source_ip=client_ip, details=f"Exceeded 5 OTP attempts for admin '{username}'")
            flash("Maximum OTP verification attempts exceeded. Please log in again.", "danger")
            return redirect(url_for("admin_ui.admin_login"))

        if AdminSecurityManager.verify_otp_code(otp_code, otp_hash):
            # Single-use OTP: Clear pending MFA state
            AdminSecurityManager.clear_pending_mfa(pending_token_str)

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

            audit_repo.log_event("MFA", "OTP_VERIFIED", "SUCCESS", username=username, source_ip=client_ip, details=f"OTP verified successfully for admin '{username}'")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "SUCCESS", username=username, source_ip=client_ip, details=f"Administrator MFA Session Established for '{username}'")
            flash(f"MFA Verification Successful! Welcome to the Administrator Portal, {username}.", "success")
            return redirect(next_url)
        else:
            remaining = max(0, 5 - attempts)
            audit_repo.log_event("MFA", "OTP_VERIFY_FAILED", "FAILED", username=username, source_ip=client_ip, details=f"Invalid OTP code (attempt {attempts}/5) for admin '{username}'")
            flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "danger")

    return render_template("admin/admin_verify_otp.html", username=username)


@admin_bp.route("/logout")
def admin_logout():
    """Clears administrative session namespace and redirects to /admin/login."""
    client_ip = get_client_ip(request)
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

    return render_template(
        "admin/admin_dashboard.html",
        active_page="admin_dashboard",
        summary=summary,
        category_distribution=cat_dist,
        priority_distribution=prio_dist,
        source_distribution=src_dist,
        daily_trends=daily_trends,
        recent_audits=recent_audits,
    )


@admin_bp.route("/collectors")
@admin_required
def admin_collectors():
    """Protected Collectors Overview & Controls."""
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
    level = request.args.get("level", "ALL")
    module = request.args.get("module", "ALL")
    search_q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
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

    return render_template(
        "admin/admin_logs.html",
        active_page="admin_logs",
        logs=app_logs_res.get("logs", []),
        audit_logs=audit_logs_res.get("logs", []),
        pagination=app_logs_res,
        stats=stats,
        selected_level=level,
        selected_module=module,
        search_query=search_q,
        active_tab=tab,
    )


@admin_bp.route("/configuration")
@admin_required
def admin_configuration():
    """Protected YAML Configuration Editor."""
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
    """Protected User Management & Account Administration."""
    if request.method == "POST":
        action = request.form.get("action")
        client_ip = get_client_ip(request)

        if action == "create_user":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()
            role = request.form.get("role", "Operator").strip()

            valid, msg = AdminSecurityManager.validate_password_strength(password)
            if not valid and role in ("Super Admin", "Administrator"):
                flash(f"Admin Password Weak: {msg}", "danger")
            else:
                try:
                    user_repo.create_user(username=username, email=email, password=password, role=role)
                    audit_repo.log_event("USER_MGMT", "CREATE_USER", "SUCCESS", username=session.get("admin_username"), source_ip=client_ip, details=f"Admin '{session.get('admin_username')}' created user '{username}' with role '{role}'")
                    flash(f"User '{username}' created successfully as {role}.", "success")
                except ValueError as e:
                    flash(str(e), "danger")

    users_list = user_repo.list_users()
    return render_template(
        "admin/admin_users.html",
        active_page="admin_users",
        users=users_list,
    )


@admin_bp.route("/reports")
@admin_required
def admin_reports():
    """Protected Reports Center."""
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
    """Protected Email Provider Diagnostics & Health Control."""
    res = api_service.check_smtp_health()
    return render_template(
        "admin/admin_email.html",
        active_page="admin_email",
        smtp_health=res,
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
                try:
                    admin_repo.update_password(resolved_admin_id, new_pw)
                    audit_repo.log_event(
                        "AUTH",
                        "ADMIN_PASSWORD_CHANGE",
                        "SUCCESS",
                        user_id=None,
                        username=resolved_username,
                        source_ip=client_ip,
                        details=f"Admin '{resolved_username}' password updated successfully",
                    )
                    flash("Administrator password updated successfully.", "success")
                    return redirect(url_for("admin_ui.admin_profile"))
                except Exception as e:
                    from src.core.logging import get_logger
                    get_logger(__name__).error(f"Error updating admin password: {e}")
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
    )

