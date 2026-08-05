"""
Flask Application Factory for CyberScout AI Web Dashboard.
"""

from pathlib import Path
from flask import Flask, jsonify, request, session

from dashboard.config import DashboardConfig
from dashboard.routes import (
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


def create_app(config_class=DashboardConfig) -> Flask:
    """Application factory for Flask Web Dashboard."""
    # Ensure database is safely initialized and seeded on deployment
    from src.database.connection import DatabaseManager
    from src.database.seed import SeedManager

    db_mgr = DatabaseManager()
    db_mgr.initialize_database()
    seed_mgr = SeedManager(db_mgr)
    seed_mgr.run_all_seeds()

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(config_class)

    # Secure Session Cookies
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Register Blueprints
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

    @app.context_processor
    def inject_user():
        """Injects active user session details into Jinja2 templates."""
        return {
            "current_user": {
                "id": session.get("user_id"),
                "username": session.get("username", "Guest"),
                "role": session.get("role", "Viewer"),
                "is_authenticated": bool(session.get("user_id")),
            }
        }

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
        return jsonify({"status": "failed", "error": "Internal Server Error", "detail": str(e)}), 200

    @app.errorhandler(404)
    def handle_404_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"status": "failed", "error": "API endpoint not found"}), 200
        return ("<h2>404 Not Found</h2>", 404)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=DashboardConfig.HOST, port=DashboardConfig.PORT, debug=True)
