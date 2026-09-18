"""
Flask Application Factory for CyberScout AI Web Dashboard.
"""

import os
import secrets
from pathlib import Path
from flask import Flask, Response, g, jsonify, redirect, request, session, url_for

from dashboard.config import DashboardConfig
from dashboard.routes import (
    admin_api_bp,
    admin_bp,
    analytics_bp,
    api_bp,
    auth_bp,
    collectors_bp,
    configuration_bp,
    dashboard_bp,
    health_bp,
    knowledge_bp,
    logs_bp,
    notifications_bp,
    opportunities_bp,
    production_bp,
    quality_bp,
    scheduler_bp,
    system_bp,
    external_trigger_bp,
    insights_bp,
)

BASE_DIR = Path(__file__).resolve().parent


def create_app(config_class=DashboardConfig, db_manager=None) -> Flask:
    """Application factory for Flask Web Dashboard."""
    # Run exponential backoff startup health check
    from src.database.connection import DatabaseManager
    from src.database.seed import SeedManager
    from src.core.logging import get_logger

    logger = get_logger(__name__)
    db_mgr = db_manager or DatabaseManager()
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
    app.config.from_object(config_class)
    setattr(app, "db_manager", db_mgr)

    # Fail-closed SECRET_KEY verification (SEC-06)
    if hasattr(config_class, "get_secret_key"):
        app.config["SECRET_KEY"] = config_class.get_secret_key()
    elif not app.config.get("TESTING") and (app.config.get("APP_ENV") == "production" or os.environ.get("RAILWAY_ENVIRONMENT")):
        from dashboard.config import INSECURE_DEFAULT_SECRETS
        secret = app.config.get("SECRET_KEY")
        if not secret or secret in INSECURE_DEFAULT_SECRETS or len(secret) < 16:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable "
                "is missing or insecure in production. Application cannot start safely."
            )

    if not app.config.get("TESTING"):
        db_connected = db_mgr.check_connection_with_backoff(max_retries=5)
        if db_connected:
            try:
                db_mgr.initialize_database()
            except Exception as e:
                logger.error(f"Error during schema initialization: {e}. Dashboard continuing in Degraded Mode.")
        else:
            logger.warning("Database unreachable on boot. CyberScout AI starting in Degraded Mode.")

    # Register Database Log Handler for structured app log persistence (idempotent)
    try:
        from src.core.logging import DatabaseLogHandler
        import logging
        root_logger = logging.getLogger()
        if not any(isinstance(h, DatabaseLogHandler) for h in root_logger.handlers):
            db_handler = DatabaseLogHandler()
            db_handler.setLevel(logging.INFO)
            root_logger.addHandler(db_handler)
    except Exception as e:
        logger.warning(f"Could not register DatabaseLogHandler: {e}")

    # Secure Session Cookie Configuration (Phase 3 Hardening SEC-06)
    from datetime import timedelta
    app.config["SESSION_COOKIE_NAME"] = "cyberscout_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    is_prod = (
        os.getenv("CYBERSCOUT_ENV") == "production"
        or app.config.get("APP_ENV") == "production"
        or os.getenv("FLASK_ENV") == "production"
        or os.getenv("ENV") == "production"
        or bool(os.getenv("RAILWAY_ENVIRONMENT"))
    )
    if is_prod and not app.config.get("TESTING"):
        app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "true").lower() != "false"
    else:
        app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=1)

    # Server-Side Session Interface (PostgreSQL-backed opaque sessions)
    from dashboard.sessions import PostgresSessionInterface
    app.session_interface = PostgresSessionInterface()

    # Reverse Proxy Header Handling (Render / Cloudflare / Nginx)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


    # Register Blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(opportunities_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(collectors_bp)
    app.register_blueprint(scheduler_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(configuration_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(external_trigger_bp)
    app.register_blueprint(insights_bp)

    @app.before_request
    def assign_request_id():
        """Extracts and validates X-Request-ID or generates a unique correlation ID."""
        import re
        req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
        if req_id and isinstance(req_id, str):
            clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", req_id.strip())[:64]
            g.request_id = clean_id if clean_id else secrets.token_hex(16)
        else:
            g.request_id = secrets.token_hex(16)
        g.correlation_id = g.request_id

    @app.before_request
    def check_first_run_setup():
        """Redirects unconfigured application to /setup if no administrator accounts exist."""
        if request.endpoint and (
            request.endpoint in (
                "auth_ui.setup",
                "auth_ui.login",
                "auth_ui.register",
                "auth_ui.forgot_password",
                "auth_ui.reset_password",
                "admin_ui.admin_login",
                "dashboard_ui.landing",
                "static",
                "health.health_status",
                "health.api_health",
                "health.health_liveness",
                "health.health_readiness",
            )
            or request.path.startswith("/api/health")
            or request.path.startswith("/health")
            or request.path.startswith("/api/external")
            or request.path.startswith("/api/scheduler")
            or request.path.startswith("/setup")
        ):
            return None
        try:
            from src.database.admin_repository import AdminRepository
            from src.database.user_repository import UserRepository
            admin_repo = AdminRepository()
            user_repo = UserRepository()
            if not admin_repo.has_admin() and not user_repo.has_admin():
                return redirect(url_for("auth_ui.setup"))
        except Exception:
            pass
        return None

    @app.before_request
    def generate_csp_nonce():
        """Generates a cryptographically secure random nonce per HTTP response."""
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def inject_template_context():
        """Injects active user session, admin session details, CSRF token, CSP nonce, and app version into Jinja2 templates."""
        from src.core.version import get_version_info
        
        token = session.get("admin_csrf_token") or session.get("user_csrf_token")
        if not token:
            token = secrets.token_hex(32)
            session["user_csrf_token"] = token
            session["admin_csrf_token"] = token

        user_id = session.get("user_id") or session.get("admin_user_id")
        saved_count = 0
        if user_id:
            try:
                from src.database.opportunity_repository import OpportunityRepository
                saved_count = OpportunityRepository().count_saved_opportunities(str(user_id))
            except Exception:
                saved_count = 0

        return {
            "app_info": get_version_info(),
            "csrf_token": token,
            "csp_nonce": getattr(g, "csp_nonce", ""),
            "saved_count": saved_count,
            "current_user": {
                "id": session.get("user_id"),
                "username": session.get("username", "Guest"),
                "role": session.get("role", "Viewer"),
                "is_authenticated": bool(session.get("user_id")),
            },
            "current_admin": {
                "id": session.get("admin_user_id"),
                "username": session.get("admin_username", "Administrator"),
                "role": session.get("admin_role", "Super Admin"),
                "is_authenticated": bool(session.get("admin_authenticated")),
                "csrf_token": token,
            },
        }

    @app.route("/robots.txt")
    def robots_txt():
        """Hardens route discovery by disallowing crawler access to protected and admin endpoints."""
        content = "User-agent: *\nDisallow: /admin/\nDisallow: /admin/*\nDisallow: /api/\nDisallow: /dashboard\nDisallow: /opportunities\nDisallow: /analytics\n"
        return Response(content, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        """Public sitemap containing public landing, login, and registration routes only."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>/</loc></url>
  <url><loc>/login</loc></url>
  <url><loc>/register</loc></url>
</urlset>"""
        return Response(xml, mimetype="application/xml")

    @app.after_request
    def apply_security_headers(response):
        """Applies OWASP Top 10 Security Headers, strict CSP with per-response nonce, anti-caching, and removes version disclosure."""
        nonce = getattr(g, "csp_nonce", "")
        nonce_part = f"'nonce-{nonce}'" if nonce else ""
        script_src = f"'self' {nonce_part}".strip()

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src {script_src}; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)
        req_id = getattr(g, "request_id", "")
        if req_id:
            response.headers["X-Request-ID"] = req_id

        if not request.path.startswith("/static") and not request.path.startswith("/health") and not request.path.startswith("/api/health") and request.path not in ("/", "/robots.txt", "/sitemap.xml"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    @app.errorhandler(500)
    def handle_500_error(e):
        req_id = getattr(g, "request_id", "unknown")
        logger.error(f"500 Internal Server Error [request_id={req_id}] on {request.path}: {e}", exc_info=True)
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/") or request.headers.get("Accept") == "application/json":
            return jsonify({"status": "failed", "error": "Internal Server Error", "request_id": req_id}), 500
        return jsonify({"status": "failed", "error": "An unexpected server error occurred. Please try again later.", "request_id": req_id}), 500

    @app.errorhandler(401)
    def handle_401_error(e):
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/") or request.headers.get("Accept") == "application/json":
            return jsonify({"status": "failed", "error": "Unauthorized. Authentication required."}), 401
        return redirect(url_for("auth_ui.login", next=request.path))

    @app.errorhandler(403)
    def handle_403_error(e):
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/") or request.headers.get("Accept") == "application/json":
            return jsonify({"status": "failed", "error": "Forbidden. Insufficient permissions."}), 403
        return redirect(url_for("dashboard_ui.index"))

    @app.errorhandler(409)
    def handle_409_error(e):
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/") or request.headers.get("Accept") == "application/json":
            return jsonify({"status": "failed", "error": "Conflict. A scan or process is already running."}), 409
        return jsonify({"status": "failed", "error": "Conflict. Action cannot be completed in current state."}), 409

    @app.errorhandler(413)
    def handle_413_error(e):
        logger.warning(f"413 Request Entity Too Large on {request.path}: {e}")
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/") or request.headers.get("Accept") == "application/json":
            return jsonify({"status": "failed", "error": "Payload Too Large. Request body exceeds maximum limit."}), 413
        return jsonify({"status": "failed", "error": "Request entity exceeds maximum permitted size."}), 413


    @app.errorhandler(404)
    def handle_404_error(e):
        if (
            request.path.startswith("/api/")
            or request.path.startswith("/admin/api/")
            or request.headers.get("Accept") == "application/json"
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return jsonify({"status": "error", "error": "Endpoint not found"}), 404
        if request.path.startswith("/static") or request.path == "/favicon.ico":
            return ("File Not Found", 404)
        return redirect(url_for("dashboard_ui.landing"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=DashboardConfig.HOST, port=DashboardConfig.PORT, debug=DashboardConfig.DEBUG)
