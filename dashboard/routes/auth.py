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
    """Renders User Account Profile page with self-only password update and OTP verification."""
    client_ip = get_client_ip(request)
    if not session.get("user_id"):
        return redirect(url_for("auth_ui.login", next=request.path))

    # Ensure user CSRF token is present in session
    if "user_csrf_token" not in session:
        session["user_csrf_token"] = secrets.token_hex(32)

    user_id = session.get("user_id")
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

        # Action 1: Cancel Pending OTP
        if action == "cancel_pw_otp":
            if pending_token:
                AdminSecurityManager.clear_pending_password_change(pending_token)
                session.pop("user_pending_pw_token", None)
            flash("Password change cancelled.", "info")
            return redirect(url_for("auth_ui.profile"))

        # Action 2: Resend OTP Code
        elif action == "resend_pw_otp":
            if not pending_state or pending_state.get("target_type") != "user" or pending_state.get("account_id") != user_id:
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
            AdminSecurityManager.update_pending_password_change_otp(pending_token, new_otp_hash, new_expires_at)

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
            if not pending_state or pending_state.get("target_type") != "user" or pending_state.get("account_id") != user_id:
                flash("No active password change request found or session expired. Please start again.", "warning")
                session.pop("user_pending_pw_token", None)
                return redirect(url_for("auth_ui.profile"))

            # Check expiration
            if int(time.time()) > pending_state.get("expires_at", 0):
                AdminSecurityManager.clear_pending_password_change(pending_token)
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
            attempts = AdminSecurityManager.increment_pending_password_change_attempts(pending_token)
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
    )
