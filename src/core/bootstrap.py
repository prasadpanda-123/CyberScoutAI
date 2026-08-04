"""
Central Application Bootstrapper and Lifecycle Manager for CyberScout AI.

Wires together Configuration, Logging, SQLite Database, Repositories,
Migration Engine, Seed Data, and Scheduler into a single CyberScoutApp.
"""

import sys
from typing import Optional

from src.core.config import Config, config
from src.core.constants import DATA_DIR, LOGS_DIR, REPORTS_DIR
from src.core.context import AppContext, RepositoryContainer
from src.core.exceptions import ConfigurationError, DatabaseError, SchedulerError
from src.core.health import HealthMonitor
from src.core.logging import get_logger, setup_logging
from src.core.version import format_banner, get_version_info
from src.database.connection import DatabaseManager
from src.database.migrations import MigrationManager
from src.database.seed import SeedManager
from src.scheduler.manager import SchedulerManager

logger = get_logger(__name__)


class CyberScoutApp:
    """
    Central Application Container managing the complete CyberScout AI lifecycle.
    """

    def __init__(self, config_files: Optional[list] = None):
        self.config_files = config_files
        self.context: Optional[AppContext] = None
        self.is_initialized = False

    def startup(self) -> AppContext:
        """
        Executes deterministic startup pipeline:
        Env -> Config -> Logging -> Directories -> SQLite -> Migrations -> Seed -> Repositories -> Scheduler -> AppContext.

        Returns:
            Instantiated AppContext.
        """
        try:
            # 0. Load Environment Variables from .env file
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass

            # 1. Load Configuration
            cfg = Config(config_files=self.config_files)

            # 2. Setup Logging System
            log_level = cfg.get("logging.level", "INFO")
            log_file = cfg.get("logging.file", "cyberscout.log")
            max_bytes = cfg.get("logging.max_bytes", 10485760)
            backup_count = cfg.get("logging.backup_count", 5)

            log_instance = setup_logging(
                level=log_level,
                log_file_name=log_file,
                max_bytes=max_bytes,
                backup_count=backup_count,
            )

            logger.info("Starting CyberScout AI Application Initialization...")

            # 3. Create Runtime Directories
            for d in [DATA_DIR, LOGS_DIR, REPORTS_DIR]:
                d.mkdir(parents=True, exist_ok=True)

            # 4. Initialize SQLite Database & Schema
            db_mgr = DatabaseManager()
            db_mgr.initialize_database()

            if not db_mgr.ping():
                raise DatabaseError("SQLite database health check ping failed.")

            # 5. Apply Pending Migrations
            mig_mgr = MigrationManager(db_mgr)
            mig_mgr.apply_migrations()
            current_version = mig_mgr.get_current_version()

            # 6. Seed Default Records
            seed_mgr = SeedManager(db_mgr)
            seed_mgr.run_all_seeds()

            # 7. Instantiate Repositories
            repos = RepositoryContainer.create_all(db_mgr)

            # 8. Instantiate Scheduler Manager
            scheduler = SchedulerManager()

            # 9. Build AppContext
            self.context = AppContext(
                config_instance=cfg,
                logger_instance=log_instance,
                db_manager=db_mgr,
                repositories=repos,
                scheduler=scheduler,
            )

            self.is_initialized = True

            # 10. Display Clean Startup Banner
            banner = format_banner(
                env=cfg.get("app_env", "development"),
                db_status="CONNECTED & VERIFIED",
                db_version=current_version,
            )
            logger.info(f"\n{banner}")
            logger.info("Application initialization pipeline completed successfully.")

            return self.context

        except ConfigurationError as e:
            logger.critical(f"Configuration startup failure: {e}")
            sys.exit(1)
        except DatabaseError as e:
            logger.critical(f"Database startup failure: {e}")
            sys.exit(1)
        except Exception as e:
            logger.critical(f"Fatal error during application startup: {e}", exc_info=True)
            sys.exit(1)

    def shutdown(self) -> None:
        """
        Executes clean shutdown sequence:
        Scheduler -> Database -> Logging teardown.
        """
        logger.info("Initiating CyberScout AI application shutdown sequence...")
        if self.context:
            if self.context.scheduler:
                self.context.scheduler.shutdown()
            if self.context.db_manager:
                self.context.db_manager.close()
        self.is_initialized = False
        logger.info("Application shutdown completed cleanly.")


# Legacy compatibility alias
AppManager = CyberScoutApp
