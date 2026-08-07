"""
Authentication and Role-Based Access Control (RBAC) Decorators for CyberScout AI.
"""

from functools import wraps
from flask import flash, jsonify, redirect, request, session, url_for


def login_required(f):
    """
    Decorator enforcing user authentication for Flask view functions and API endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id") and not session.get("admin_authenticated"):
            if request.path.startswith("/api/") or request.headers.get("Accept") == "application/json":
                return jsonify({"status": "failed", "error": "Authentication required", "login_url": "/login"}), 401
            return redirect(url_for("auth_ui.login", next=request.path))
        return f(*args, **kwargs)

    return decorated_function


def roles_required(*allowed_roles):
    """
    Decorator enforcing Role-Based Access Control (RBAC) permissions.
    Valid Roles: 'Super Admin', 'Administrator', 'Operator', 'Viewer'.
    Super Admin has full system access to all endpoints.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                if request.path.startswith("/api/") or request.headers.get("Accept") == "application/json":
                    return jsonify({"status": "failed", "error": "Authentication required", "login_url": "/login"}), 401
                return redirect(url_for("auth_ui.login", next=request.path))

            user_role = session.get("role", "Viewer")

            # Admin role bypasses role restrictions
            if user_role in ("Admin", "admin", "Super Admin", "Administrator"):
                return f(*args, **kwargs)

            if user_role not in allowed_roles:
                if request.path.startswith("/api/") or request.headers.get("Accept") == "application/json":
                    return jsonify({"status": "failed", "error": f"Access denied. Required roles: {', '.join(allowed_roles)}"}), 403
                flash(f"Access Denied: Your role '{user_role}' is not authorized to access this section.", "danger")
                return redirect(url_for("dashboard_ui.index"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(f):
    """
    Decorator enforcing strict Administrative Portal access control.
    Requires isolated session flag `session['admin_authenticated'] = True`
    and administrative role ('Admin', 'admin', 'Super Admin', 'Administrator').

    Behavior:
    - Not logged in -> 302 Redirect to `/admin/login` (HTML) or HTTP 401 JSON (API).
    - Logged in as normal user -> HTTP 403 Forbidden (HTML/JSON).
    - Logged in as admin -> Access granted.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_api = (
            request.path.startswith("/admin/api/")
            or request.path.startswith("/api/")
            or request.headers.get("Accept") == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )

        admin_auth = session.get("admin_authenticated", False)
        admin_role = session.get("admin_role")

        if not admin_auth or not admin_role:
            # Check if logged in as a normal user attempting to access admin route
            if session.get("user_id"):
                if is_api:
                    return jsonify({
                        "status": "failed",
                        "error": "Forbidden: Administrative privilege required"
                    }), 403
                return ("<div style='font-family:sans-serif; text-align:center; padding:50px;'><h1>403 Forbidden</h1><p>Access Denied: Administrative Portal access requires admin credentials.</p></div>", 403)

            # Not logged in at all
            if is_api:
                return jsonify({
                    "status": "failed",
                    "error": "Admin authentication required",
                    "login_url": "/admin/login"
                }), 401
            return redirect(url_for("admin_ui.admin_login", next=request.path))

        if admin_role not in ("Admin", "admin", "Super Admin", "Administrator"):
            if is_api:
                return jsonify({
                    "status": "failed",
                    "error": "Forbidden: Insufficient administrative privileges"
                }), 403
            return ("<div style='font-family:sans-serif; text-align:center; padding:50px;'><h1>403 Forbidden</h1><p>Access Denied: Administrative role required.</p></div>", 403)

        return f(*args, **kwargs)

    return decorated_function

