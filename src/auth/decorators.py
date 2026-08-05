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
        if not session.get("user_id"):
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

            # Super Admin bypasses all role restrictions
            if user_role == "Super Admin":
                return f(*args, **kwargs)

            if user_role not in allowed_roles:
                if request.path.startswith("/api/") or request.headers.get("Accept") == "application/json":
                    return jsonify({"status": "failed", "error": f"Access denied. Required roles: {', '.join(allowed_roles)}"}), 403
                flash(f"Access Denied: Your role '{user_role}' is not authorized to access this section.", "danger")
                return redirect(url_for("dashboard_ui.index"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator
