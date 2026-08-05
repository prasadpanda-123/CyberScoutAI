"""
Routes package for CyberScout AI dashboard.
"""

from dashboard.routes.auth import auth_bp
from dashboard.routes.dashboard import dashboard_bp
from dashboard.routes.opportunities import opportunities_bp
from dashboard.routes.analytics import analytics_bp
from dashboard.routes.collectors import collectors_bp
from dashboard.routes.scheduler import scheduler_bp
from dashboard.routes.notifications import notifications_bp
from dashboard.routes.knowledge import knowledge_bp
from dashboard.routes.configuration import configuration_bp
from dashboard.routes.logs import logs_bp
from dashboard.routes.health import health_bp
from dashboard.routes.system import system_bp
from dashboard.routes.api import api_bp
from dashboard.routes.quality import quality_bp
from dashboard.routes.production import production_bp

__all__ = [
    "auth_bp",
    "dashboard_bp",
    "opportunities_bp",
    "analytics_bp",
    "collectors_bp",
    "scheduler_bp",
    "notifications_bp",
    "knowledge_bp",
    "configuration_bp",
    "logs_bp",
    "health_bp",
    "system_bp",
    "api_bp",
    "quality_bp",
    "production_bp",
]
