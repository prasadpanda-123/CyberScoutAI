"""
Seed Data Manager for CyberScout AI.

Loads and inserts default sources, default preferences, and taxonomy keywords into PostgreSQL.
"""

from typing import Optional

from src.core.config import config
from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.database.keyword_repository import KeywordRepository
from src.database.source_repository import SourceRepository
from src.database.stats_repository import PreferencesRepository
from src.models.keyword import Keyword

logger = get_logger(__name__)


class SeedManager:
    """
    Manages loading and seeding default database records.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.source_repo = SourceRepository(self.db_manager)
        self.pref_repo = PreferencesRepository(self.db_manager)
        self.kw_repo = KeywordRepository(self.db_manager)

    def seed_sources(self) -> int:
        """Seeds default sources from configuration and authoritative catalog."""
        count = 0
        sources_cfg = config.get("sources", {})
        if sources_cfg:
            count += self.source_repo.sync_from_config(sources_cfg)
        try:
            count += self.source_repo.sync_authoritative_sources()
        except Exception as e:
            logger.warning(f"Authoritative sources seeding notice: {e}")
        logger.info(f"Seeded {count} sources into database.")
        return count

    def seed_preferences(self) -> int:
        """Seeds default system preferences."""
        defaults = {
            "app.theme": "dark",
            "digest.max_items": "20",
            "digest.include_beginner": "true",
            "ranking.free_boost": "30",
        }
        count = 0
        for k, v in defaults.items():
            self.pref_repo.set_preference(k, v)
            count += 1
        logger.info(f"Seeded {count} default preferences into database.")
        return count

    def seed_keywords(self) -> int:
        """Seeds taxonomy keywords from config into database."""
        keywords_cfg = config.get("keywords", {})
        if not keywords_cfg:
            return 0

        categories = keywords_cfg.get("categories", keywords_cfg)
        count = 0
        if isinstance(categories, dict):
            for domain, domain_obj in categories.items():
                terms_list = domain_obj.get("terms", []) if isinstance(domain_obj, dict) else domain_obj
                if isinstance(terms_list, list):
                    for term_item in terms_list:
                        term_str = term_item if isinstance(term_item, str) else term_item.get("term") if isinstance(term_item, dict) else None
                        if term_str:
                            kw = Keyword(term=term_str.strip().lower(), domain=domain)
                            self.kw_repo.save_keyword(kw)
                            count += 1
        logger.info(f"Seeded {count} taxonomy keywords into database.")
        return count

    def seed_users(self) -> int:
        """Seeds default Admin user ('admin@cyberscout.ai') into Admins table safely with production guard (SEC-01)."""
        import os
        from src.database.admin_repository import AdminRepository
        from src.auth.admin_auth import AdminSecurityManager

        admin_repo = AdminRepository(self.db_manager)

        app_env = (os.getenv("APP_ENV") or os.getenv("CYBERSCOUT_ENV") or "").strip().lower()
        is_production = app_env == "production"

        initial_admin_pw = (
            os.getenv("CYBERSCOUT_INITIAL_ADMIN_PASSWORD", "").strip()
            or os.getenv("INITIAL_ADMIN_PASSWORD", "").strip()
        )

        # In production environments, never seed a hardcoded default password
        if is_production and not initial_admin_pw:
            logger.info("Production environment: skipping default admin seeding. Complete first-run setup via /setup.")
            return 0

        admin_password = initial_admin_pw or "Admin@CyberScout2026!"
        is_strong, _ = AdminSecurityManager.validate_password_strength(admin_password)
        if not is_strong and is_production:
            logger.warning("Configured production initial admin password violates complexity requirements. Skipping seeding.")
            return 0

        # Seed primary Admin account into Admins table if not present by email or username
        existing_admin = admin_repo.get_by_email("admin@cyberscout.ai") or admin_repo.get_by_username("admin")
        if not existing_admin:
            try:
                admin_repo.create_admin(
                    username="admin",
                    email="admin@cyberscout.ai",
                    password=admin_password,
                    role="Admin",
                )
                logger.info("Seeded primary Admin account ('admin@cyberscout.ai') into Admins table.")
                return 1
            except Exception as e:
                logger.debug(f"Admin seeding collision handled safely: {e}")
                return 0
        return 0

    def run_all_seeds(self) -> None:
        """Executes all database seed operations idempotently."""
        logger.info("Executing database seed data population...")
        self.seed_sources()
        self.seed_preferences()
        self.seed_keywords()
        self.seed_users()
        logger.info("Database seeding complete.")
