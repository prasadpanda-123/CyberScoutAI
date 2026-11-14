import html
import hashlib
import hmac
import os
import secrets
from urllib.parse import quote, urlsplit
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from src.auth.admin_auth import AdminSecurityManager
from src.database.admin_repository import AdminRepository
from src.database.audit_log_repository import AuditLogRepository
from src.database.password_reset_repository import PasswordResetRepository
from src.database.login_attempt_repository import LoginAttemptRepository
from src.database.user_repository import UserRepository
from src.utils.ip_utils import get_client_ip
from src.core.logging import get_logger

logger = get_logger(__name__)
auth_bp = Blueprint("auth_ui", __name__)
user_repo = UserRepository()
admin_repo = AdminRepository()
audit_repo = AuditLogRepository()
password_reset_repo = PasswordResetRepository()
_auth_rate_limit_repo = None


def _rate_limit_repository():
    global _auth_rate_limit_repo
    if _auth_rate_limit_repo is None:
        _auth_rate_limit_repo = LoginAttemptRepository(db_manager=user_repo.db_manager)
    return _auth_rate_limit_repo


def _public_app_origin() -> str:
    """Returns the configured canonical origin used for security-sensitive links."""
    public_url = (current_app.config.get("PUBLIC_APP_URL") or "").strip()
    parsed = urlsplit(public_url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("PUBLIC_APP_URL must be a valid HTTP(S) origin.")
    if current_app.config.get("APP_ENV") == "production" and parsed.scheme != "https":
        raise RuntimeError("PUBLIC_APP_URL must use HTTPS in production.")
    try:
        parsed.port
    except ValueError as exc:
        raise RuntimeError("PUBLIC_APP_URL contains an invalid port.") from exc
    return f"{parsed.scheme}://{parsed.netloc}"


def _send_password_reset_email(email: str, username: str, raw_token: str) -> bool:
    try:
        from src.notifier.providers.brevo_provider import BrevoEmailProvider
        reset_link = f"{_public_app_origin()}/reset-password/{quote(raw_token, safe='')}"
        safe_username = html.escape(username, quote=True)
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #2d3748; border-radius: 8px; background: #0f172a; color: #f8fafc;">
          <h2 style="color: #38bdf8;">CyberScout AI Password Reset</h2>
          <p>Hello {safe_username},</p>
          <p>We received a request to reset your password. Click the button below to set a new password:</p>
          <div style="margin: 24px 0;">
            <a href="{reset_link}" style="background: #0284c7; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">Reset Password</a>
          </div>
          <p style="font-size: 12px; color: #94a3b8;">This link expires in 1 hour. If you did not make this request, you can safely ignore this email.</p>
        </div>
        """
        plain_content = f"Hello {username},\n\nReset your password here: {reset_link}\n\nExpires in 1 hour."
        provider = BrevoEmailProvider()
        res = provider.send_email(
            html_content=html_content,
            plain_content=plain_content,
            subject="CyberScout AI — Password Reset Request",
            recipient=email,
        )
        return bool(res.get("status") == "success")
    except Exception as e:
        logger.warning(f"Could not dispatch password reset email via Brevo: {e}")
        return False


@auth_bp.before_request
def ensure_csrf_token():
    """Ensures a CSRF token is present in the session for public authentication routes."""
    try:
        if "user_csrf_token" not in session and "admin_csrf_token" not in session:
            session["user_csrf_token"] = AdminSecurityManager.generate_csrf_token()
    except Exception as e:
        logger.warning(f"Error ensuring user_csrf_token: {e}")


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """One-Time First-Run Setup flow when no administrator accounts exist."""
    client_ip = get_client_ip(request)
    if admin_repo.has_admin() or user_repo.has_admin():
        flash("First-run setup is permanently disabled because administrator accounts already exist.", "info")
        return redirect(url_for("admin_ui.admin_login"))

    setup_secret = os.environ.get("INITIAL_ADMIN_SETUP_TOKEN", "").strip()
    production = (current_app.config.get("APP_ENV") or os.environ.get("CYBERSCOUT_ENV", "")).lower() in ("production", "prod")
    if production and not setup_secret:
        return "Initial administrator setup is disabled until INITIAL_ADMIN_SETUP_TOKEN is configured.", 503

    if request.method == "POST":
        if setup_secret:
            try:
                setup_allowed = _rate_limit_repository().check_and_record_rate_limit(
                    client_ip, "initial-admin-setup", "initial_admin_setup", max_attempts=8, window_minutes=15
                )
            except Exception as e:
                logger.error(f"Initial administrator setup throttle is unavailable: {e}")
                return "Initial administrator setup is temporarily unavailable.", 503
            if not setup_allowed:
                return "Too many initial administrator setup attempts. Try again later.", 429
        submitted_setup_secret = request.form.get("setup_token", "").strip()
        if (production and not setup_secret) or (setup_secret and not secrets.compare_digest(setup_secret, submitted_setup_secret)):
            audit_repo.log_event("AUTH", "SETUP_FAILED", "TOKEN_INVALID", source_ip=client_ip, details="Initial administrator setup authorization failed")
            return render_template("setup.html", setup_token_required=bool(setup_secret)), 403

        csrf_token = request.form.get("csrf_token", "").strip()
        expected_csrf = session.get("admin_csrf_token") or session.get("user_csrf_token")
        if not expected_csrf or not csrf_token or not AdminSecurityManager.verify_csrf_token(expected_csrf, csrf_token):
            audit_repo.log_event("AUTH", "SETUP_FAILED", "CSRF_FAILED", source_ip=client_ip, details="CSRF token validation failed on first-run setup")
            flash("CSRF validation failed. Please try again.", "danger")
            return render_template("setup.html", setup_token_required=bool(setup_secret)), 400

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "warning")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        elif not AdminSecurityManager.validate_password_strength(password)[0]:
            flash(AdminSecurityManager.validate_password_strength(password)[1], "danger")
        else:
            try:
                admin_account = admin_repo.create_admin(
                    username=username,
                    email=email,
                    password=password,
                    role="Super Admin",
                    first_admin_only=True,
                )
                audit_repo.log_event("AUTH", "SETUP_COMPLETE", "SUCCESS", user_id=admin_account["id"], username=username, source_ip=client_ip, details="Initial super admin created in Admins table")
                session.clear()
                flash(f"First-run setup complete! Super Admin '{username}' created successfully. Please log in to complete MFA setup.", "success")
                return redirect(url_for("admin_ui.admin_login"))
            except Exception as e:
                audit_repo.log_event("AUTH", "SETUP_FAILED", "FAILED", username=username, source_ip=client_ip, details="Initial administrator account creation failed")
                logger.error(f"Initial administrator setup failed: {e}")
                flash("Setup could not be completed. Please verify the deployment configuration and try again.", "danger")

    return render_template("setup.html", setup_token_required=bool(setup_secret))


from src.utils.url_utils import is_safe_internal_url

def _is_safe_url(target: str) -> bool:
    """Verifies target redirect URL is a safe internal relative path."""
    return is_safe_internal_url(target)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Renders login page and handles user authentication."""
    client_ip = get_client_ip(request)
    if session.get("user_id"):
        return redirect(url_for("dashboard_ui.index"))

    if request.method == "POST":
        is_json = request.is_json or (request.headers.get("Accept") == "application/json" and request.get_json(silent=True) is not None)
        json_data = request.get_json(silent=True) if is_json else None

        if is_json and json_data:
            identifier = (json_data.get("identifier") or json_data.get("username") or "").strip()
            password = (json_data.get("password") or "").strip()
            csrf_token = (json_data.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()
            raw_next = json_data.get("next") or request.args.get("next")
        else:
            identifier = (request.form.get("identifier") or request.form.get("username") or "").strip()
            password = request.form.get("password", "").strip()
            csrf_token = (request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()
            raw_next = request.form.get("next") or request.args.get("next")

        next_url = raw_next if (raw_next and _is_safe_url(raw_next)) else url_for("dashboard_ui.index")

        # 0. CSRF Token Validation
        session_csrf = session.get("user_csrf_token") or session.get("admin_csrf_token")
        if not session_csrf or not csrf_token or not secrets.compare_digest(session_csrf, csrf_token):
            audit_repo.log_event("AUTH", "USER_LOGIN", "CSRF_FAILED", username=identifier or "Anonymous", source_ip=client_ip, details="CSRF token validation failed on user login")
            if is_json:
                return jsonify({"status": "failed", "error": "CSRF validation failed. Please try again."}), 400
            flash("CSRF validation failed. Please try again.", "danger")
            raw_next_arg = request.args.get("next", "")
            safe_next_arg = raw_next_arg if _is_safe_url(raw_next_arg) else ""
            return render_template("login.html", next=safe_next_arg), 400

        # 1. Distributed Rate Limiting & Abuse Protection
        try:
            login_attempt_allowed = AdminSecurityManager.consume_login_attempt(
                client_ip, identifier, attempt_type="user_login"
            )
        except Exception as e:
            logger.error(f"Distributed user login throttle is unavailable: {e}")
            if is_json:
                return jsonify({"status": "failed", "error": "Service temporarily unavailable. Please try again shortly."}), 503
            flash("Service temporarily unavailable. Please try again shortly.", "danger")
            return render_template("login.html", next=next_url), 503

        if not login_attempt_allowed:
            audit_repo.log_event("AUTH", "USER_LOGIN_LOCKED", "FAILED", username=identifier or "Anonymous", source_ip=client_ip, details="User login attempt while locked out")
            if is_json:
                return jsonify({"status": "failed", "error": "Account temporarily locked due to 5 consecutive failed login attempts. Please wait 15 minutes."}), 429
            flash("Account temporarily locked due to 5 consecutive failed login attempts. Please wait 15 minutes.", "danger")
            raw_next_arg = request.args.get("next", "")
            safe_next_arg = raw_next_arg if _is_safe_url(raw_next_arg) else ""
            return render_template("login.html", next=safe_next_arg)

        db_outage = False
        try:
            user = user_repo.authenticate(identifier, password)
        except Exception as e:
            err_str = str(e).lower()
            if any(term in err_str for term in ("connection", "could not connect", "timeout", "pool", "network", "operationalerror", "server closed")):
                logger.error(f"Database outage during user authentication: {e}")
                db_outage = True
            else:
                logger.error(f"User authentication error: {e}")
            user = None

        if db_outage:
            try:
                audit_repo.log_event("AUTH", "USER_LOGIN_ERROR", "SERVICE_UNAVAILABLE", username=identifier or "Anonymous", source_ip=client_ip, details="Database unavailable during authentication")
            except Exception:
                pass
            if is_json:
                return jsonify({"status": "failed", "error": "Service temporarily unavailable. Please try again in a few moments."}), 503
            flash("Service temporarily unavailable. Please try again in a few moments.", "danger")
            raw_next_arg = request.args.get("next", "")
            safe_next_arg = raw_next_arg if _is_safe_url(raw_next_arg) else ""
            return render_template("login.html", next=safe_next_arg), 503

        if user:
            # Enforce Portal Isolation: Admin accounts cannot authenticate via user login
            if user.get("role") in ("Admin", "admin", "Super Admin", "Administrator"):
                audit_repo.log_event("AUTH", "USER_LOGIN_REJECTED", "PORTAL_ISOLATION", user_id=user["id"], username=user["username"], source_ip=client_ip, details="Admin attempted user login portal; rejected to prevent enumeration")
                if is_json:
                    return jsonify({"status": "failed", "error": "Invalid username/email or password."}), 401
                flash("Invalid username/email or password.", "danger")
                raw_next_arg = request.args.get("next", "")
                safe_next_arg = raw_next_arg if _is_safe_url(raw_next_arg) else ""
                return render_template("login.html", next=safe_next_arg), 401

            # Reset failed login attempt history on success
            AdminSecurityManager.reset_failed_attempts(client_ip, identifier, attempt_type="user_login")

            # Session Fixation Defense: Clear existing session dictionary before setting authenticated session keys
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            session["user_csrf_token"] = AdminSecurityManager.generate_csrf_token()

            audit_repo.log_event("AUTH", "USER_LOGIN", "SUCCESS", user_id=user["id"], username=user["username"], source_ip=client_ip, details="User login successful")
            if is_json:
                return jsonify({
                    "status": "success",
                    "message": f"Welcome back, {user['username']}!",
                    "user": {
                        "id": user["id"],
                        "username": user["username"],
                        "email": user["email"],
                        "role": user["role"],
                        "is_admin": False,
                    },
                    "csrf_token": session["user_csrf_token"],
                    "redirect": next_url,
                }), 200
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(next_url)
        else:
            audit_repo.log_event("AUTH", "USER_LOGIN", "FAILED", username=identifier or "Anonymous", source_ip=client_ip, details="Invalid credentials")
            if is_json:
                return jsonify({"status": "failed", "error": "Invalid username/email or password."}), 401
            flash("Invalid username/email or password.", "danger")

    raw_next_arg = request.args.get("next", "")
    safe_next_arg = raw_next_arg if _is_safe_url(raw_next_arg) else ""
    if request.args.get("legacy") == "1":
        return render_template("login.html", next=safe_next_arg)
    return render_template("react_shell.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Renders registration page and handles new user creation."""
    client_ip = get_client_ip(request)
    if session.get("user_id"):
        return redirect(url_for("dashboard_ui.index"))

    if request.method == "POST":
        is_json = request.is_json or (request.headers.get("Accept") == "application/json" and request.get_json(silent=True) is not None)
        json_data = request.get_json(silent=True) if is_json else None

        if is_json and json_data:
            username = (json_data.get("username") or "").strip()
            email = (json_data.get("email") or "").strip()
            password = (json_data.get("password") or "").strip()
            confirm_password = (json_data.get("confirm_password") or password).strip()
            csrf_token = (json_data.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()
        else:
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()
            csrf_token = (request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()

        expected_csrf = session.get("user_csrf_token") or session.get("admin_csrf_token")
        if not expected_csrf or not csrf_token or not secrets.compare_digest(expected_csrf, csrf_token):
            audit_repo.log_event("AUTH", "USER_REGISTER", "CSRF_FAILED", source_ip=client_ip, details="CSRF validation failed on registration")
            if is_json:
                return jsonify({"status": "failed", "error": "CSRF validation failed. Please try again."}), 400
            flash("CSRF validation failed. Please try again.", "danger")
            return render_template("register.html"), 400

        # Security Hardening (Phase 1): Always enforce default Viewer role server-side.
        role = "Viewer"

        if not username or not email or not password:
            msg = "All fields are required."
            if is_json:
                return jsonify({"status": "failed", "error": msg}), 400
            flash(msg, "warning")
        elif len(password) < 8:
            msg = "Password must be at least 8 characters long."
            if is_json:
                return jsonify({"status": "failed", "error": msg}), 400
            flash(msg, "danger")
        elif password != confirm_password:
            msg = "Passwords do not match."
            if is_json:
                return jsonify({"status": "failed", "error": msg}), 400
            flash(msg, "danger")
        else:
            try:
                user = user_repo.create_user(username=username, email=email, password=password, role=role)
                audit_repo.log_event("AUTH", "USER_REGISTER", "SUCCESS", user_id=user["id"], username=username, source_ip=client_ip, details="New student user registered")
                if is_json:
                    return jsonify({"status": "success", "message": "Registration successful! Please log in."}), 201
                flash("Registration successful! Please log in with your credentials.", "success")
                return redirect(url_for("auth_ui.login"))
            except ValueError as e:
                audit_repo.log_event("AUTH", "USER_REGISTER", "FAILED", username=username, source_ip=client_ip, details=f"Registration validation failure: {e}")
                if is_json:
                    return jsonify({"status": "failed", "error": str(e)}), 400
                flash(str(e), "danger")

    if request.args.get("legacy") == "1":
        return render_template("register.html")
    return render_template("react_shell.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Revokes the active session using a CSRF-protected POST."""
    client_ip = get_client_ip(request)
    json_payload = request.get_json(silent=True)
    raw_csrf_token = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or (json_payload.get("csrf_token") if isinstance(json_payload, dict) else "")
        or request.form.get("csrf_token", "")
    )
    csrf_token = raw_csrf_token.strip() if isinstance(raw_csrf_token, str) else ""
    expected_csrf = session.get("user_csrf_token") or session.get("admin_csrf_token")
    if not expected_csrf or not csrf_token or not secrets.compare_digest(expected_csrf, csrf_token):
        return jsonify({"status": "failed", "error": "CSRF validation failed."}), 400

    uid = session.get("user_id")
    uname = session.get("username")
    if uid:
        audit_repo.log_event("AUTH", "USER_LOGOUT", "SUCCESS", user_id=uid, username=uname, source_ip=client_ip, details="User logged out")
    session.clear()
    return jsonify({"status": "success"})


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Handles password reset request flow with CSRF protection and token generation."""
    client_ip = get_client_ip(request)
    if request.method == "POST":
        is_json = request.is_json or (request.headers.get("Accept") == "application/json" and request.get_json(silent=True) is not None)
        json_data = request.get_json(silent=True) if is_json else None

        if is_json and isinstance(json_data, dict):
            raw_email = json_data.get("email")
            raw_csrf = json_data.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or ""
            email = raw_email.strip().lower() if isinstance(raw_email, str) else ""
            csrf_token = raw_csrf.strip() if isinstance(raw_csrf, str) else ""
        else:
            email = request.form.get("email", "").strip().lower()
            csrf_token = (request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or "").strip()

        expected_csrf = session.get("user_csrf_token") or session.get("admin_csrf_token")
        if not expected_csrf or not csrf_token or not secrets.compare_digest(expected_csrf, csrf_token):
            audit_repo.log_event("AUTH", "FORGOT_PASSWORD", "CSRF_FAILED", source_ip=client_ip, details="CSRF validation failed on forgot-password")
            if is_json:
                return jsonify({"status": "failed", "error": "CSRF validation failed. Please try again."}), 400
            flash("CSRF validation failed. Please try again.", "danger")
            return render_template("forgot_password.html"), 400

        try:
            rate_repo = _rate_limit_repository()
            email_key = hmac.new(
                str(current_app.config.get("SECRET_KEY", "")).encode("utf-8"),
                email.encode("utf-8", errors="ignore"),
                hashlib.sha256,
            ).hexdigest()
            allowed_ip = rate_repo.check_and_record_rate_limit(
                client_ip, "forgot-password", "password_reset_ip", max_attempts=10, window_minutes=15
            )
            allowed_email = rate_repo.check_and_record_rate_limit(
                "password-reset", email_key, "password_reset_email", max_attempts=3, window_minutes=60
            )
        except Exception as e:
            logger.error(f"Password reset rate-limit storage is unavailable: {e}")
            return jsonify({"status": "unavailable", "message": "Password reset is temporarily unavailable. Please try again later."}), 503

        generic_message = "If an account matches that address, reset instructions will be sent."
        if not allowed_ip or not allowed_email:
            if is_json:
                return jsonify({"status": "success", "message": generic_message}), 200
            flash(generic_message, "info")
            return redirect(url_for("auth_ui.login"))

        if email:
            target_user = user_repo.get_by_email(email)
            if target_user:
                raw_token = secrets.token_urlsafe(32)
                try:
                    password_reset_repo.store_token(str(target_user["id"]), raw_token)
                    _send_password_reset_email(target_user["email"], target_user.get("username", "User"), raw_token)
                except Exception as e:
                    logger.error(f"Could not prepare password reset request: {e}")

        audit_repo.log_event("AUTH", "FORGOT_PASSWORD", "REQUESTED", source_ip=client_ip, details="Password reset requested")
        if is_json:
            return jsonify({"status": "success", "message": generic_message}), 200
        flash(generic_message, "info")
        return redirect(url_for("auth_ui.login"))

    if request.args.get("legacy") == "1":
        return render_template("forgot_password.html")
    return render_template("react_shell.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Renders reset password page and applies new credentials."""
    client_ip = get_client_ip(request)
    if request.method == "GET":
        try:
            token_record = password_reset_repo.get_valid_token(token)
        except Exception as e:
            logger.error(f"Could not verify password reset token: {e}")
            token_record = None
        if not token_record:
            flash("Password reset link is invalid or has expired. Please request a new one.", "danger")
            return redirect(url_for("auth_ui.forgot_password"))
        return render_template("reset_password.html", token=token)

    if request.method == "POST":
        csrf_token = request.form.get("csrf_token", "").strip()
        expected_csrf = session.get("user_csrf_token") or session.get("admin_csrf_token")
        if not expected_csrf or not csrf_token or not secrets.compare_digest(expected_csrf, csrf_token):
            flash("CSRF validation failed. Please try again.", "danger")
            return render_template("reset_password.html", token=token), 400

        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not new_password or len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("reset_password.html", token=token)
        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html", token=token)

        try:
            password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
            user_id = password_reset_repo.complete_password_reset(token, password_hash)
            if not user_id:
                flash("Password reset link is invalid or has expired. Please request a new one.", "danger")
                return redirect(url_for("auth_ui.forgot_password"))
            session.clear()
            audit_repo.log_event("AUTH", "PASSWORD_RESET_COMPLETE", "SUCCESS", user_id=user_id, source_ip=client_ip, details="User successfully completed password reset flow")
            flash("Password updated successfully! Please sign in with your new credentials.", "success")
            return redirect(url_for("auth_ui.login"))
        except Exception as e:
            logger.error(f"Error completing password reset: {e}")
            flash("Could not reset your password. Please try again.", "danger")

    return render_template("reset_password.html", token=token)


@auth_bp.route("/profile", methods=["GET", "POST"])
def profile():
    """Renders User Account Profile page with self-only password update and OTP verification."""
    client_ip = get_client_ip(request)
    raw_uid = session.get("user_id")
    if not raw_uid:
        return redirect(url_for("auth_ui.login", next=request.path))

    import uuid
    try:
        user_id = str(uuid.UUID(str(raw_uid).strip()))
    except (ValueError, TypeError, AttributeError):
        session.clear()
        flash("Invalid session identifier. Please log in again.", "warning")
        return redirect(url_for("auth_ui.login"))

    # Ensure user CSRF token is present in session
    if "user_csrf_token" not in session:
        session["user_csrf_token"] = secrets.token_hex(32)

    username = session.get("username", "User")

    user_record = user_repo.get_by_id(user_id) if user_id else None
    email_val = (user_record.get("email") if user_record else None) or session.get("email", "")
    role_val = (user_record.get("role") if user_record else None) or session.get("role", "Student / User")
    is_active_val = user_record.get("is_active", True) if user_record else True

    from src.auth.admin_auth import AdminSecurityManager
    import time
    from werkzeug.security import generate_password_hash

    pending_token = session.get("user_pending_pw_token")
    pending_state = AdminSecurityManager.get_pending_password_change(pending_token) if pending_token else None

    # Auto-prune expired pending state on GET
    if pending_state and (int(time.time()) > pending_state.get("expires_at", 0) or pending_state.get("account_id") != user_id):
        AdminSecurityManager.clear_pending_password_change(pending_token)
        session.pop("user_pending_pw_token", None)
        pending_state = None

    if request.method == "POST":
        submitted_csrf = request.form.get("csrf_token", "").strip()
        session_csrf = session.get("user_csrf_token", "")
        if not submitted_csrf or not session_csrf or not secrets.compare_digest(submitted_csrf, session_csrf):
            audit_repo.log_event("AUTH", "PASSWORD_CHANGE", "CSRF_FAILED", user_id=user_id, username=username, source_ip=client_ip, details="CSRF token validation failed on password change")
            flash("CSRF validation failed. Please try again.", "danger")
            return redirect(url_for("auth_ui.profile"))

        action = request.form.get("action", "request_pw_change")

        # Action: Save Personalization / Career Preferences
        if action == "save_preferences":
            skills_raw = request.form.get("skills", "")
            interests_raw = request.form.get("interests", "")
            categories_list = request.form.getlist("preferred_categories")
            types_list = request.form.getlist("preferred_types")
            remote_val = request.form.get("prefers_remote")
            location_val = request.form.get("preferred_location", "").strip()
            exp_val = request.form.get("experience_level", "").strip()

            from src.intelligence.skill_normalizer import normalize_skill_list
            skills = normalize_skill_list([s.strip() for s in skills_raw.split(",") if s.strip()])
            interests = [i.strip() for i in interests_raw.split(",") if i.strip()]
            prefers_remote = None
            if remote_val == "true":
                prefers_remote = True
            elif remote_val == "false":
                prefers_remote = False

            from src.models.recommendation_models import UserPreferencesDTO
            from src.database.user_preferences_repository import UserPreferencesRepository

            prefs = UserPreferencesDTO(
                skills=skills,
                interests=interests,
                preferred_categories=categories_list,
                preferred_types=types_list,
                prefers_remote=prefers_remote,
                preferred_location=location_val if location_val else None,
                experience_level=exp_val if exp_val else None,
            )
            try:
                UserPreferencesRepository(db_manager=user_repo.db_manager).save_preferences(user_id, prefs)
                audit_repo.log_event(
                    "USER_PROFILE",
                    "PREFERENCES_UPDATED",
                    "SUCCESS",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details="User updated career discovery preferences",
                )
                flash("Career preferences updated successfully.", "success")
            except Exception as e:
                logger.error(f"Failed to save preferences for user {user_id}: {e}")
                flash("Failed to save career preferences. Please try again.", "danger")
            return redirect(url_for("auth_ui.profile"))

        # Action 1: Cancel Pending OTP
        elif action == "cancel_pw_otp":
            if pending_token:
                AdminSecurityManager.clear_pending_password_change(pending_token)
                session.pop("user_pending_pw_token", None)
            flash("Password change cancelled.", "info")
            return redirect(url_for("auth_ui.profile"))

        # Action 2: Resend OTP Code
        elif action == "resend_pw_otp":
            if not pending_token or not pending_state or pending_state.get("target_type") != "user" or pending_state.get("account_id") != user_id:
                flash("No active password change request found. Please initiate a new request.", "warning")
                session.pop("user_pending_pw_token", None)
                return redirect(url_for("auth_ui.profile"))

            # Enforce 30-second cooldown
            now = int(time.time())
            last_resend = pending_state.get("last_resend_at", 0)
            if now - last_resend < 30:
                wait_sec = 30 - (now - last_resend)
                flash(f"Please wait {wait_sec} seconds before requesting a new code.", "warning")
                return redirect(url_for("auth_ui.profile"))

            new_otp = AdminSecurityManager.generate_otp_code()
            new_otp_hash = AdminSecurityManager.hash_otp_code(new_otp)
            new_expires_at = now + 300
            AdminSecurityManager.update_pending_password_change_otp(str(pending_token), new_otp_hash, new_expires_at)

            try:
                from src.notifier.email_sender import EmailSender
                sender = EmailSender()
                subject = "CyberScout AI — Account Password Change Verification Code"
                plain_body = f"Hello {username},\n\nYour 6-digit password verification code is:\n\n   {new_otp}\n\nThis code is valid for 5 minutes. Do not share this code.\n\nCyberScout AI Security"
                html_body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif; background-color:#0f172a; color:#f8fafc; padding:30px;">
                <div style="max-width:500px; margin:0 auto; background-color:#1e293b; padding:30px; border-radius:10px; border:1px solid #334155;">
                  <h2 style="color:#0ea5e9; margin-top:0;">CyberScout AI Security</h2>
                  <p>Account Password Change Verification Code:</p>
                  <div style="background-color:#0f172a; border:1px solid #0ea5e9; color:#0ea5e9; font-size:32px; font-weight:bold; letter-spacing:5px; text-align:center; padding:15px; border-radius:8px; margin:20px 0;">
                    {new_otp}
                  </div>
                  <p style="font-size:13px; color:#94a3b8;">This code is valid for 5 minutes. If you did not request this change, please inspect your account activity.</p>
                </div>
                </body></html>"""
                msg_id = sender.send_email(
                    html_content=html_body,
                    plain_content=plain_body,
                    subject=subject,
                    recipient=email_val,
                )
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_REQUESTED",
                    "SUCCESS",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details=f"Password change OTP resent to {AdminSecurityManager.mask_email(email_val)} (msg_id={msg_id})",
                )
                flash("A new verification code has been dispatched to your email.", "info")
            except Exception as e:
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_REQUESTED",
                    "DISPATCH_FAILED",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details=f"Failed to resend password change OTP: {e}",
                )
                flash("Could not send verification code. Please try again.", "danger")
            return redirect(url_for("auth_ui.profile"))

        # Action 3: Verify OTP and Finalize Password Update
        elif action == "verify_pw_otp":
            if not pending_token or not pending_state or pending_state.get("target_type") != "user" or pending_state.get("account_id") != user_id:
                flash("No active password change request found or session expired. Please start again.", "warning")
                session.pop("user_pending_pw_token", None)
                return redirect(url_for("auth_ui.profile"))

            # Check expiration
            if int(time.time()) > pending_state.get("expires_at", 0):
                AdminSecurityManager.clear_pending_password_change(str(pending_token))
                session.pop("user_pending_pw_token", None)
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_FAILED",
                    "EXPIRED",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details="User password change OTP expired",
                )
                flash("Verification code has expired. Please initiate the password change again.", "danger")
                return redirect(url_for("auth_ui.profile"))

            # Increment and check attempt limit
            attempts = AdminSecurityManager.increment_pending_password_change_attempts(str(pending_token))
            if attempts > 5:
                AdminSecurityManager.clear_pending_password_change(pending_token)
                session.pop("user_pending_pw_token", None)
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_FAILED",
                    "MAX_ATTEMPTS_EXCEEDED",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details="Exceeded maximum OTP attempts for password change",
                )
                flash("Maximum verification attempts exceeded. Please request a new password change.", "danger")
                return redirect(url_for("auth_ui.profile"))

            otp_input = request.form.get("otp_code", "").strip()
            if not AdminSecurityManager.verify_otp_code(otp_input, pending_state["otp_hash"]):
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_FAILED",
                    "INVALID_CODE",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details=f"Invalid OTP entered for password change (attempt {attempts}/5)",
                )
                flash(f"Invalid verification code. {max(0, 5 - attempts)} attempts remaining.", "danger")
                return redirect(url_for("auth_ui.profile"))

            # OTP Verified Successfully!
            new_password_hash = pending_state["new_password_hash"]
            try:
                user_repo.update_password_hash(user_id, new_password_hash)
                AdminSecurityManager.clear_pending_password_change(pending_token)
                session.pop("user_pending_pw_token", None)

                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE_OTP_VERIFIED",
                    "SUCCESS",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details="Password change OTP verified successfully",
                )
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE",
                    "SUCCESS",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details="User password updated successfully after OTP verification",
                )
                flash("Password updated successfully.", "success")
                return redirect(url_for("auth_ui.profile"))
            except Exception as e:
                audit_repo.log_event(
                    "AUTH",
                    "PASSWORD_CHANGE",
                    "FAILED",
                    user_id=user_id,
                    username=username,
                    source_ip=client_ip,
                    details=f"Database error during password update: {e}",
                )
                flash("Failed to update password. Please try again.", "danger")
                return redirect(url_for("auth_ui.profile"))

        # Action 4 (Default): Validate Password Form & Initiate OTP Verification
        else:
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
                if not user_repo.verify_password(user_id, current_pw):
                    audit_repo.log_event("AUTH", "PASSWORD_CHANGE", "INVALID_CURRENT_PW", user_id=user_id, username=username, source_ip=client_ip, details="Incorrect current password provided")
                    flash("Current password is incorrect.", "danger")
                else:
                    pw_hash = generate_password_hash(new_pw, method="pbkdf2:sha256")
                    otp_code = AdminSecurityManager.generate_otp_code()
                    otp_hash = AdminSecurityManager.hash_otp_code(otp_code)
                    expires_at = int(time.time()) + 300

                    new_pending_token = AdminSecurityManager.store_pending_password_change(
                        target_type="user",
                        account_id=user_id,
                        username=username,
                        email=email_val,
                        new_password_hash=pw_hash,
                        otp_hash=otp_hash,
                        expires_at=expires_at,
                    )
                    session["user_pending_pw_token"] = new_pending_token

                    # Send OTP email
                    try:
                        from src.notifier.email_sender import EmailSender
                        sender = EmailSender()
                        subject = "CyberScout AI — Account Password Change Verification Code"
                        plain_body = f"Hello {username},\n\nYour 6-digit password verification code is:\n\n   {otp_code}\n\nThis code is valid for 5 minutes. Do not share this code.\n\nCyberScout AI Security"
                        html_body = f"""<!DOCTYPE html><html><body style="font-family:sans-serif; background-color:#0f172a; color:#f8fafc; padding:30px;">
                        <div style="max-width:500px; margin:0 auto; background-color:#1e293b; padding:30px; border-radius:10px; border:1px solid #334155;">
                          <h2 style="color:#0ea5e9; margin-top:0;">CyberScout AI Security</h2>
                          <p>Account Password Change Verification Code:</p>
                          <div style="background-color:#0f172a; border:1px solid #0ea5e9; color:#0ea5e9; font-size:32px; font-weight:bold; letter-spacing:5px; text-align:center; padding:15px; border-radius:8px; margin:20px 0;">
                            {otp_code}
                          </div>
                          <p style="font-size:13px; color:#94a3b8;">This code is valid for 5 minutes. If you did not request this change, please inspect your account activity.</p>
                        </div>
                        </body></html>"""

                        msg_id = sender.send_email(
                            html_content=html_body,
                            plain_content=plain_body,
                            subject=subject,
                            recipient=email_val,
                        )
                        audit_repo.log_event(
                            "AUTH",
                            "PASSWORD_CHANGE_OTP_REQUESTED",
                            "SUCCESS",
                            user_id=user_id,
                            username=username,
                            source_ip=client_ip,
                            details=f"User password change OTP dispatched to {AdminSecurityManager.mask_email(email_val)} (msg_id={msg_id})",
                        )
                        flash("A 6-digit verification code has been sent to your registered email address.", "info")
                    except Exception as e:
                        AdminSecurityManager.clear_pending_password_change(new_pending_token)
                        session.pop("user_pending_pw_token", None)
                        audit_repo.log_event(
                            "AUTH",
                            "PASSWORD_CHANGE_OTP_REQUESTED",
                            "DISPATCH_FAILED",
                            user_id=user_id,
                            username=username,
                            source_ip=client_ip,
                            details=f"Failed to dispatch password change OTP email: {e}",
                        )
                        flash("Could not send verification code. Please try again.", "danger")
                    return redirect(url_for("auth_ui.profile"))

    preferences = None
    try:
        from src.database.user_preferences_repository import UserPreferencesRepository
        preferences = UserPreferencesRepository(db_manager=user_repo.db_manager).get_preferences(user_id)
    except Exception as pe:
        logger.warning(f"Could not load preferences for user {user_id}: {pe}")

    if request.args.get("legacy") != "1":
        return render_template("react_shell.html")

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
        pending_otp=bool(pending_state),
        masked_email=AdminSecurityManager.mask_email(pending_state.get("email") or email_val) if pending_state else "",
        preferences=preferences,
    )

