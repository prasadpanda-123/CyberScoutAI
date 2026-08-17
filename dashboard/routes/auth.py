import secrets
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from src.database.audit_log_repository import AuditLogRepository
from src.database.user_repository import UserRepository
from src.utils.ip_utils import get_client_ip

auth_bp = Blueprint("auth_ui", __name__)
user_repo = UserRepository()
audit_repo = AuditLogRepository()


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """One-Time First-Run Setup flow when no administrator accounts exist."""
    client_ip = get_client_ip(request)
    if user_repo.has_admin():
        flash("First-run setup is permanently disabled because administrator accounts already exist.", "info")
        return redirect(url_for("auth_ui.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "warning")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            try:
                user = user_repo.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role="Super Admin",
                )
                audit_repo.log_event("AUTH", "SETUP_COMPLETE", "SUCCESS", user_id=user["id"], username=username, source_ip=client_ip, details="Initial super admin created")
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["email"] = user["email"]
                session["role"] = user["role"]
                flash(f"First-run setup complete! Super Admin '{username}' created successfully.", "success")
                return redirect(url_for("dashboard_ui.index"))
            except Exception:
                audit_repo.log_event("AUTH", "SETUP_FAILED", "FAILED", username=username, source_ip=client_ip, details="Setup account creation error")
                flash("Setup error occurred during account creation.", "danger")

    return render_template("setup.html")


def _is_safe_url(target: str) -> bool:
    """Verifies target redirect URL is a safe internal relative path."""
    if not target or not isinstance(target, str):
        return False
    target = target.strip()
    return target.startswith("/") and not target.startswith("//") and not target.startswith("/\\")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Renders login page and handles user authentication."""
    client_ip = get_client_ip(request)
    if session.get("user_id"):
        return redirect(url_for("dashboard_ui.index"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "").strip()
        raw_next = request.form.get("next") or request.args.get("next")
        next_url = raw_next if (raw_next and _is_safe_url(raw_next)) else url_for("dashboard_ui.index")

        user = user_repo.authenticate(identifier, password)
        if user:
            # Enforce Portal Isolation: Admin accounts must authenticate via /admin/login
            if user.get("role") in ("Admin", "admin", "Super Admin", "Administrator"):
                audit_repo.log_event("AUTH", "USER_LOGIN_REDIRECT", "PORTAL_ISOLATION", user_id=user["id"], username=user["username"], source_ip=client_ip, details="Admin attempted user login portal; redirected to /admin/login")
                flash("Administrator accounts must authenticate through the dedicated Administrator Portal at /admin/login.", "warning")
                return redirect(url_for("admin_ui.admin_login"))

            # Session Fixation Defense: Clear existing session dictionary before setting authenticated session keys
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            session["role"] = user["role"]

            audit_repo.log_event("AUTH", "USER_LOGIN", "SUCCESS", user_id=user["id"], username=user["username"], source_ip=client_ip, details="User login successful")
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(next_url)
        else:
            audit_repo.log_event("AUTH", "USER_LOGIN", "FAILED", username=identifier or "Anonymous", source_ip=client_ip, details="Invalid credentials")
            flash("Invalid username/email or password.", "danger")

    raw_next_arg = request.args.get("next", "")
    safe_next_arg = raw_next_arg if _is_safe_url(raw_next_arg) else ""
    return render_template("login.html", next=safe_next_arg)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Renders registration page and handles new user creation."""
    client_ip = get_client_ip(request)
    if session.get("user_id"):
        return redirect(url_for("dashboard_ui.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        # Security Hardening (Phase 1): Always enforce default Viewer role server-side.
        role = "Viewer"

        if not username or not email or not password:
            flash("All fields are required.", "warning")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            try:
                user = user_repo.create_user(username=username, email=email, password=password, role=role)
                audit_repo.log_event("AUTH", "USER_REGISTER", "SUCCESS", user_id=user["id"], username=username, source_ip=client_ip, details="New student user registered")
                flash("Registration successful! Please log in with your credentials.", "success")
                return redirect(url_for("auth_ui.login"))
            except ValueError as e:
                audit_repo.log_event("AUTH", "USER_REGISTER", "FAILED", username=username, source_ip=client_ip, details=f"Registration validation failure: {e}")
                flash(str(e), "danger")

    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    """Clears active session and redirects to public landing page '/'."""
    client_ip = get_client_ip(request)
    uid = session.get("user_id")
    uname = session.get("username")
    if uid:
        audit_repo.log_event("AUTH", "USER_LOGOUT", "SUCCESS", user_id=uid, username=uname, source_ip=client_ip, details="User logged out")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("dashboard_ui.landing"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Handles password reset request flow."""
    client_ip = get_client_ip(request)
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        audit_repo.log_event("AUTH", "FORGOT_PASSWORD", "REQUESTED", source_ip=client_ip, details=f"Password reset requested for {email}")
        flash(f"If an account exists for '{email}', password reset instructions have been dispatched.", "info")
        return redirect(url_for("auth_ui.login"))
    return render_template("forgot_password.html")


@auth_bp.route("/profile", methods=["GET", "POST"])
def profile():
    """Renders minimal User Account Profile page with self-only password update and CSRF protection."""
    client_ip = get_client_ip(request)
    if not session.get("user_id"):
        return redirect(url_for("auth_ui.login", next=request.path))

    # Ensure user CSRF token is present in session
    if "user_csrf_token" not in session:
        session["user_csrf_token"] = secrets.token_hex(32)

    user_id = session.get("user_id")
    username = session.get("username", "User")

    if request.method == "POST":
        submitted_csrf = request.form.get("csrf_token", "").strip()
        session_csrf = session.get("user_csrf_token", "")
        if not submitted_csrf or not session_csrf or not secrets.compare_digest(submitted_csrf, session_csrf):
            audit_repo.log_event("AUTH", "PASSWORD_CHANGE", "CSRF_FAILED", user_id=user_id, username=username, source_ip=client_ip, details="CSRF token validation failed on password change")
            flash("CSRF validation failed. Please try again.", "danger")
            return redirect(url_for("auth_ui.profile"))

        current_pw = request.form.get("current_password", "").strip()
        new_pw = request.form.get("new_password", "").strip()
        confirm_pw = request.form.get("confirm_password", "").strip()

        if not current_pw or not new_pw or not confirm_pw:
            flash("All password fields are required.", "warning")
        elif new_pw != confirm_pw:
            flash("New password and confirmation do not match.", "danger")
        elif len(new_pw) < 8:
            flash("Password must be at least 8 characters long.", "warning")
        elif current_pw == new_pw:
            flash("New password cannot be identical to your current password.", "warning")
        else:
            # Verify current password strictly against authenticated user_id
            if user_repo.verify_password(user_id, current_pw):
                try:
                    user_repo.update_password(user_id, new_pw)
                    audit_repo.log_event("AUTH", "PASSWORD_CHANGE", "SUCCESS", user_id=user_id, username=username, source_ip=client_ip, details="User password updated successfully")
                    flash("Password updated successfully.", "success")
                    return redirect(url_for("auth_ui.profile"))
                except Exception:
                    audit_repo.log_event("AUTH", "PASSWORD_CHANGE", "FAILED", user_id=user_id, username=username, source_ip=client_ip, details="Database error during password update")
                    flash("Failed to update password. Please try again.", "danger")
            else:
                audit_repo.log_event("AUTH", "PASSWORD_CHANGE", "INVALID_CURRENT_PW", user_id=user_id, username=username, source_ip=client_ip, details="Incorrect current password provided")
                flash("Current password is incorrect.", "danger")

    user_record = user_repo.get_by_id(user_id) if user_id else None
    email_val = (user_record.get("email") if user_record else None) or session.get("email", "")
    role_val = (user_record.get("role") if user_record else None) or session.get("role", "Student / User")
    is_active_val = user_record.get("is_active", True) if user_record else True

    return render_template(
        "profile.html",
        active_page="profile",
        csrf_token=session.get("user_csrf_token", ""),
        user_info={
            "username": username,
            "email": email_val,
            "role": role_val,
            "is_active": is_active_val,
        },
    )
