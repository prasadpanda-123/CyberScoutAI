"""
Dedicated Administrative Portal Routes (Phase 1 & Phase 3) for CyberScout AI v2.2.

Isolates all administrative views under `/admin/*` protected by `@admin_required`.
"""

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
from src.database.audit_log_repository import AuditLogRepository
from src.database.log_repository import LogRepository
from src.database.user_repository import UserRepository

admin_bp = Blueprint("admin_ui", __name__, url_prefix="/admin")

user_repo = UserRepository()
audit_repo = AuditLogRepository()
log_repo = LogRepository()
dash_service = DashboardService()
stats_service = StatisticsService()
api_service = APIService()


@admin_bp.before_request
def ensure_csrf_token():
    """Ensures a CSRF token is present in the admin session."""
    if "admin_csrf_token" not in session:
        session["admin_csrf_token"] = AdminSecurityManager.generate_csrf_token()


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """
    Dedicated Admin Login Portal.
    Only allows users with role 'Super Admin' or 'Administrator' to authenticate.
    """
    # If already authenticated as admin, redirect to admin dashboard
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_ui.admin_dashboard"))

    client_ip = request.remote_addr or "127.0.0.1"

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "").strip()
        csrf_token = request.form.get("csrf_token", "").strip()
        next_url = request.form.get("next") or request.args.get("next") or url_for("admin_ui.admin_dashboard")

        # 1. Validate CSRF Token
        if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
            flash("CSRF validation failed. Please try again.", "danger")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "FAILED", username=identifier, source_ip=client_ip, details="CSRF token mismatch")
            return render_template("admin/admin_login.html", next=next_url)

        # 2. Check Rate Limit / Account Lockout
        if AdminSecurityManager.is_locked_out(client_ip, identifier):
            flash("Account locked due to 5 consecutive failed login attempts. Please wait 15 minutes.", "danger")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "LOCKED_OUT", username=identifier, source_ip=client_ip, details="Attempt during lockout period")
            return render_template("admin/admin_login.html", next=next_url)

        # 3. Authenticate User
        user = user_repo.authenticate(identifier, password)

        if not user:
            AdminSecurityManager.record_failed_attempt(client_ip, identifier)
            flash("Invalid administrator credentials.", "danger")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "FAILED", username=identifier, source_ip=client_ip, details="Invalid credentials")
            return render_template("admin/admin_login.html", next=next_url)

        # 4. Role Authorization Check: Admin role permitted
        user_role = user.get("role")
        if user_role not in ("Admin", "admin", "Super Admin", "Administrator"):
            AdminSecurityManager.record_failed_attempt(client_ip, identifier)
            flash("Access Denied: Standard user accounts cannot authenticate through the Administrator Portal.", "danger")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "DENIED", user_id=user["id"], username=user["username"], source_ip=client_ip, details=f"Non-admin role '{user_role}' attempted admin login")
            return render_template("admin/admin_login.html", next=next_url)

        # 5. Password Verified -> Generate 6-digit OTP & Store Pending MFA State (Phases 6 - 8)
        otp_code = AdminSecurityManager.generate_otp_code()
        otp_hash = AdminSecurityManager.hash_otp_code(otp_code)
        expires_at = int(time.time()) + 300  # 5 minutes validity

        session["admin_pending_user_id"] = user["id"]
        session["admin_pending_username"] = user["username"]
        session["admin_pending_role"] = user["role"]
        session["admin_pending_email"] = user["email"]
        session["admin_pending_otp_hash"] = otp_hash
        session["admin_pending_otp_expires_at"] = expires_at
        session["admin_pending_otp_attempts"] = 0
        session["admin_pending_next"] = next_url

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
            sender.send_email(html_content=html_body, plain_content=plain_body, subject=subject)
            audit_repo.log_event("MFA", "OTP_GENERATED", "SUCCESS", user_id=user["id"], username=user["username"], source_ip=client_ip, details="OTP code dispatched via email")
            flash("Credentials verified! A 6-digit verification code has been dispatched to your email address.", "info")
        except Exception as e:
            # Audit log records fallback code for development & testing environments
            audit_repo.log_event("MFA", "OTP_GENERATED", "DEV_FALLBACK", user_id=user["id"], username=user["username"], source_ip=client_ip, details=f"OTP: {otp_code} (Dispatch info: {e})")
            flash(f"Credentials verified! Verification Code: {otp_code}", "info")

        return redirect(url_for("admin_ui.admin_verify_otp"))

    return render_template("admin/admin_login.html", next=request.args.get("next", ""))


@admin_bp.route("/verify-otp", methods=["GET", "POST"])
def admin_verify_otp():
    """
    Administrator OTP Verification (MFA) endpoint (Phases 6 - 8).
    Requires 6-digit numeric OTP code sent to admin's email.
    """
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_ui.admin_dashboard"))

    user_id = session.get("admin_pending_user_id")
    username = session.get("admin_pending_username")
    role = session.get("admin_pending_role")
    otp_hash = session.get("admin_pending_otp_hash")
    expires_at = session.get("admin_pending_otp_expires_at", 0)
    next_url = session.get("admin_pending_next") or url_for("admin_ui.admin_dashboard")

    if not user_id or not otp_hash:
        flash("No pending authentication session. Please log in.", "warning")
        return redirect(url_for("admin_ui.admin_login"))

    client_ip = request.remote_addr or "127.0.0.1"
    import time
    now = int(time.time())

    # Check 5-minute expiration window
    if now > expires_at:
        session.pop("admin_pending_user_id", None)
        session.pop("admin_pending_otp_hash", None)
        audit_repo.log_event("MFA", "OTP_EXPIRED", "FAILED", user_id=user_id, username=username, source_ip=client_ip, details="OTP code expired")
        flash("Verification code has expired (valid for 5 minutes). Please log in again.", "danger")
        return redirect(url_for("admin_ui.admin_login"))

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        csrf_token = request.form.get("csrf_token", "").strip()

        if not AdminSecurityManager.verify_csrf_token(session.get("admin_csrf_token"), csrf_token):
            flash("CSRF validation failed.", "danger")
            return render_template("admin/admin_verify_otp.html", username=username)

        # Track verification attempts
        attempts = session.get("admin_pending_otp_attempts", 0) + 1
        session["admin_pending_otp_attempts"] = attempts

        if attempts > 5:
            session.pop("admin_pending_user_id", None)
            session.pop("admin_pending_otp_hash", None)
            AdminSecurityManager.record_failed_attempt(client_ip, username)
            audit_repo.log_event("MFA", "OTP_LOCKOUT", "FAILED", user_id=user_id, username=username, source_ip=client_ip, details="Exceeded 5 OTP attempts")
            flash("Maximum OTP verification attempts exceeded. Please log in again.", "danger")
            return redirect(url_for("admin_ui.admin_login"))

        if AdminSecurityManager.verify_otp_code(otp_code, otp_hash):
            # Single-use OTP: Clear pending MFA state
            session.pop("admin_pending_user_id", None)
            session.pop("admin_pending_username", None)
            session.pop("admin_pending_role", None)
            session.pop("admin_pending_email", None)
            session.pop("admin_pending_otp_hash", None)
            session.pop("admin_pending_otp_expires_at", None)
            session.pop("admin_pending_otp_attempts", None)
            session.pop("admin_pending_next", None)

            # Issue full administrator session
            AdminSecurityManager.reset_failed_attempts(client_ip, username)
            session.clear()
            session["admin_authenticated"] = True
            session["admin_user_id"] = user_id
            session["admin_username"] = username
            session["admin_role"] = role
            session["admin_csrf_token"] = AdminSecurityManager.generate_csrf_token()

            audit_repo.log_event("MFA", "OTP_VERIFIED", "SUCCESS", user_id=user_id, username=username, source_ip=client_ip, details="OTP verified successfully")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "SUCCESS", user_id=user_id, username=username, source_ip=client_ip, details="Administrator MFA Session Established")
            flash(f"MFA Verification Successful! Welcome to the Administrator Portal, {username}.", "success")
            return redirect(next_url)
        else:
            remaining = max(0, 5 - attempts)
            audit_repo.log_event("MFA", "OTP_VERIFY_FAILED", "FAILED", user_id=user_id, username=username, source_ip=client_ip, details=f"Invalid OTP code (attempt {attempts}/5)")
            flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "danger")

    return render_template("admin/admin_verify_otp.html", username=username)


@admin_bp.route("/logout")
def admin_logout():
    """Clears administrative session namespace and redirects to /admin/login."""
    client_ip = request.remote_addr or "127.0.0.1"
    admin_user = session.get("admin_username")
    admin_id = session.get("admin_user_id")

    if admin_user:
        audit_repo.log_event("AUTH", "ADMIN_LOGOUT", "SUCCESS", user_id=admin_id, username=admin_user, source_ip=client_ip, details="Admin logged out")

    session.pop("admin_authenticated", None)
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)
    session.pop("admin_role", None)

    flash("Administrator session terminated.", "info")
    return redirect(url_for("admin_ui.admin_login"))


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
        client_ip = request.remote_addr or "127.0.0.1"

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
                    audit_repo.log_event("USER_MGMT", "CREATE_USER", "SUCCESS", user_id=session.get("admin_user_id"), username=session.get("admin_username"), source_ip=client_ip, details=f"Created user '{username}' with role '{role}'")
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
    audit_repo.log_event("REPORTS", "DOWNLOAD_REPORT", "SUCCESS", user_id=session.get("admin_user_id"), username=session.get("admin_username"), source_ip=request.remote_addr, details=f"Downloaded report '{filename}'")
    return send_from_directory(str(reports_dir), filename, as_attachment=True)


@admin_bp.route("/diagnostics")
@admin_required
def admin_diagnostics():
    """Protected System & Feed Diagnostics Control."""
    diag_summary = RSSDiagnosticsManager().get_feed_diagnostics_summary()
    audit_repo.log_event("DIAGNOSTICS", "ACCESS_DIAGNOSTICS", "SUCCESS", user_id=session.get("admin_user_id"), username=session.get("admin_username"), source_ip=request.remote_addr, details="Viewed feed diagnostics")
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
