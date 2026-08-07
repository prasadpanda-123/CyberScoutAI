"""
Flask Application Factory for CyberScout AI Web Dashboard.
"""

from pathlib import Path
from flask import Flask, Response, jsonify, redirect, request, session, url_for

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
    app.db_manager = db_mgr

    db_connected = db_mgr.check_connection_with_backoff(max_retries=5)
    if db_connected:
        try:
            db_mgr.initialize_database()
            seed_mgr = SeedManager(db_mgr)
            seed_mgr.run_all_seeds()
        except Exception as e:
            logger.error(f"Error during schema initialization: {e}. Dashboard continuing in Degraded Mode.")
    else:
        logger.warning("Database unreachable on boot. CyberScout AI starting in Degraded Mode.")
    app.config.from_object(config_class)

    # Secure Session Cookies
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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

    @app.before_request
    def check_first_run_setup():
        """Redirects unconfigured application to /setup if no users exist."""
        if request.endpoint and (request.endpoint in ("auth_ui.setup", "admin_ui.admin_login", "static", "health.health_status", "health.api_health") or request.path.startswith("/api/health")):
            return None
        try:
            from src.database.user_repository import UserRepository
            user_repo = UserRepository()
            if not user_repo.has_users() and not request.path.startswith("/setup"):
                return redirect(url_for("auth_ui.setup"))
        except Exception:
            pass
        return None

    @app.context_processor
    def inject_user_and_admin():
        """Injects active user session, admin session details, and app version into Jinja2 templates."""
        from src.core.version import get_version_info
        return {
            "app_info": get_version_info(),
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
                "csrf_token": session.get("admin_csrf_token", ""),
            },
        }

    @app.route("/robots.txt")
    def robots_txt():
        """Hardens route discovery by disallowing crawler access to /admin/* endpoints."""
        content = "User-agent: *\nDisallow: /admin/\nDisallow: /admin/*\nDisallow: /api/admin/\n"
        return Response(content, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        """Public sitemap excluding administrative portal routes."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>/dashboard</loc></url>
  <url><loc>/opportunities</loc></url>
  <url><loc>/analytics</loc></url>
  <url><loc>/login</loc></url>
</urlset>"""
        return Response(xml, mimetype="application/xml")

    @app.after_request
    def apply_security_headers(response):
        """Applies OWASP Top 10 Security Headers and removes version disclosure."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)
        return response

    @app.errorhandler(500)
    def handle_500_error(e):
        logger.exception(f"500 Internal Server Error on {request.path}: {e}")
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/") or request.headers.get("Accept") == "application/json":
            return jsonify({"status": "failed", "error": "Internal Server Error", "message": str(e)}), 500
        return jsonify({"status": "failed", "error": "Internal Server Error"}), 500

    @app.errorhandler(404)
    def handle_404_error(e):
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/"):
            return jsonify({"status": "failed", "error": "API endpoint not found"}), 404
        return ("<h2>404 Not Found</h2>", 404)

    return app

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=DashboardConfig.HOST, port=DashboardConfig.PORT, debug=True)
