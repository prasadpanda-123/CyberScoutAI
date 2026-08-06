"""
Dedicated Administrative Portal Routes (Phase 1 & Phase 3) for CyberScout AI v2.2.

Isolates all administrative views under `/admin/*` protected by `@admin_required`.
"""

from pathlib import Path
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

        # 4. Role Authorization Check: Only Admin / Super Admin permitted
        user_role = user.get("role")
        if user_role not in ("Super Admin", "Administrator"):
            AdminSecurityManager.record_failed_attempt(client_ip, identifier)
            flash("Access Denied: Standard user accounts cannot authenticate through the Administrator Portal.", "danger")
            audit_repo.log_event("AUTH", "ADMIN_LOGIN", "DENIED", user_id=user["id"], username=user["username"], source_ip=client_ip, details=f"Non-admin role '{user_role}' attempted admin login")
            return render_template("admin/admin_login.html", next=next_url)

        # 5. Successful Authentication -> Session Regeneration
        AdminSecurityManager.reset_failed_attempts(client_ip, identifier)
        session.clear()
        session["admin_authenticated"] = True
        session["admin_user_id"] = user["id"]
        session["admin_username"] = user["username"]
        session["admin_role"] = user["role"]
        session["admin_csrf_token"] = AdminSecurityManager.generate_csrf_token()

        audit_repo.log_event("AUTH", "ADMIN_LOGIN", "SUCCESS", user_id=user["id"], username=user["username"], source_ip=client_ip, details="Administrator logged in successfully")
        flash(f"Administrator Portal Session Established. Welcome, {user['username']}!", "success")
        return redirect(next_url)

    return render_template("admin/admin_login.html", next=request.args.get("next", ""))


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
    summary = dash_service.get_summary_stats()
    cat_dist = stats_service.get_category_distribution()
    prio_dist = stats_service.get_priority_distribution()
    src_dist = stats_service.get_source_distribution()
    daily_trends = stats_service.get_daily_opportunity_trends()
    recent_audits = audit_repo.query_logs(limit=10).get("logs", [])

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
        "sqlite_version": "3.45.1",
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
