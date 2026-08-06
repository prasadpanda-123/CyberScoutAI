"""
Authentication & Session Routes for CyberScout AI Control Center.
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from src.database.user_repository import UserRepository

auth_bp = Blueprint("auth_ui", __name__)
user_repo = UserRepository()


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """One-Time First-Run Setup flow when no administrator accounts exist."""
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
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["email"] = user["email"]
                session["role"] = user["role"]
                flash(f"First-run setup complete! Super Admin '{username}' created successfully.", "success")
                return redirect(url_for("dashboard_ui.index"))
            except Exception as e:
                flash(f"Setup error: {e}", "danger")

    return render_template("setup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Renders login page and handles user authentication."""
    if session.get("user_id"):
        return redirect(url_for("dashboard_ui.index"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "").strip()
        next_url = request.form.get("next") or request.args.get("next") or url_for("dashboard_ui.index")

        user = user_repo.authenticate(identifier, password)
        if user:
            # Session Fixation Defense: Clear existing session dictionary before setting authenticated session keys
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['username']}! Logged in as {user['role']}.", "success")
            return redirect(next_url)
        else:
            flash("Invalid username/email or password.", "danger")

    return render_template("login.html", next=request.args.get("next", ""))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Renders registration page and handles new user creation."""
    if session.get("user_id"):
        return redirect(url_for("dashboard_ui.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        # Security Hardening (Phase 1): Always enforce default Viewer role server-side.
        # Ignore any client-submitted 'role' parameters to prevent privilege escalation.
        role = "Viewer"

        if not username or not email or not password:
            flash("All fields are required.", "warning")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            try:
                user = user_repo.create_user(username=username, email=email, password=password, role=role)
                flash("Registration successful! Please log in with your credentials.", "success")
                return redirect(url_for("auth_ui.login"))
            except ValueError as e:
                flash(str(e), "danger")

    return render_template("register.html")


@auth_bp.route("/logout")
def logout():
    """Clears active session and redirects to login."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth_ui.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Handles password reset request flow."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        flash(f"If an account exists for '{email}', password reset instructions have been dispatched.", "info")
        return redirect(url_for("auth_ui.login"))
    return render_template("forgot_password.html")
