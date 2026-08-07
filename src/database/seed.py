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
        """Seeds default sources from configuration."""
        sources_cfg = config.get("sources", {})
        if not sources_cfg:
            logger.warning("No sources configuration found to seed.")
            return 0
        count = self.source_repo.sync_from_config(sources_cfg)
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
        """Seeds default Admin user ('admin@cyberscout.ai') and cleans up extra admin accounts."""
        from src.database.user_repository import UserRepository
        user_repo = UserRepository(self.db_manager)

        # 1. Clean up legacy admin accounts except admin@cyberscout.ai
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM Users WHERE LOWER(email) != 'admin@cyberscout.ai' AND LOWER(role) LIKE '%admin%'")
            conn.commit()
        except Exception as e:
            logger.warning(f"Note during user cleanup: {e}")
        finally:
            cursor.close()

        # 2. Seed primary Admin user if not present
        existing_admin = user_repo.get_by_email("admin@cyberscout.ai")
        if not existing_admin:
            user_repo.create_user(
                username="admin",
                email="admin@cyberscout.ai",
                password="Admin@CyberScout2026!",
                role="Admin",
            )
            logger.info("Seeded primary Admin user ('admin@cyberscout.ai').")
            return 1
        else:
            # Update role to standard 'Admin'
            try:
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE Users SET role = 'Admin' WHERE LOWER(email) = 'admin@cyberscout.ai'")
                conn.commit()
                cursor.close()
            except Exception:
                pass
        return 0

    def run_all_seeds(self) -> None:
        """Executes all database seed operations idempotently."""
        logger.info("Executing database seed data population...")
        self.seed_sources()
        self.seed_preferences()
        self.seed_keywords()
        self.seed_users()
        logger.info("Database seeding complete.")
