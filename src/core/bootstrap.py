"""
Central Application Bootstrapper and Lifecycle Manager for CyberScout AI.

Wires together Configuration, Environment Variables (.env), Logging, PostgreSQL Database,
Repositories, Migration Engine, Seed Data, and Scheduler into a single CyberScoutApp.
"""

import os
from pathlib import Path
import shutil
import sys
from typing import Optional

from src.core.config import Config, config
from src.core.constants import DATA_DIR, LOGS_DIR, PROJECT_ROOT, REPORTS_DIR
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


def ensure_env_file(root_dir: Optional[Path] = None) -> bool:
    """
    Verifies existence of root-level .env file.
    If missing, automatically creates .env from .env.example template.

    Args:
        root_dir: Optional root directory path.

    Returns:
        True if .env exists or was created, False otherwise.
    """
    root = root_dir or PROJECT_ROOT
    env_file = root / ".env"
    example_file = root / ".env.example"

    if not env_file.exists() and example_file.exists():
        try:
            shutil.copy(example_file, env_file)
            logger.info("Automatically generated '.env' file from '.env.example' template.")
        except Exception as e:
            logger.warning(f"Could not auto-generate .env file: {e}")

    try:
        from dotenv import load_dotenv
        if env_file.exists():
            load_dotenv(dotenv_path=env_file, override=False)
        else:
            load_dotenv(override=False)
        return True
    except ImportError:
        logger.debug("python-dotenv not installed. Skipping .env file loading.")
        return False


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
        Env -> Config -> Logging -> Directories -> Database -> Migrations -> Seed -> Repositories -> Scheduler -> AppContext.

        Returns:
            Instantiated AppContext.
        """
        try:
            # 0. Load Environment Variables from .env file (Auto-create if missing)
            ensure_env_file()

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

            # 3. Verify Runtime Directories
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)

            # 4. Initialize Database & Run Migrations
            db_mgr = DatabaseManager()
            db_mgr.initialize_database()

            # 5. Seed Initial Database Tables
            seed_mgr = SeedManager(db_mgr)
            seed_mgr.run_all_seeds()

            # 6. Instantiate Repository Container
            repos = RepositoryContainer.create_all(db_mgr)

            # 7. Initialize Scheduler Manager
            scheduler_mgr = SchedulerManager()

            # 8. Construct Central AppContext
            self.context = AppContext(
                config_instance=cfg,
                logger_instance=logger,
                db_manager=db_mgr,
                repositories=repos,
                scheduler=scheduler_mgr,
            )

            self.is_initialized = True
            logger.info("\n" + format_banner())
            logger.info("Application initialization pipeline completed successfully.")
            return self.context

        except Exception as e:
            logger.critical(f"CyberScoutApp startup failed: {e}", exc_info=True)
            raise ConfigurationError(f"Application bootstrap failed: {e}", original_exception=e)

    def shutdown(self) -> None:
        """Executes graceful shutdown sequence for background threads and database connections."""
        if not self.is_initialized or not self.context:
            logger.warning("Shutdown called on uninitialized CyberScoutApp instance.")
            return

        logger.info("Initiating CyberScout AI application shutdown sequence...")
        try:
            if self.context.scheduler:
                self.context.scheduler.shutdown()

            if self.context.db_manager:
                self.context.db_manager.close_connection()

            self.is_initialized = False
            logger.info("Application shutdown completed cleanly.")
        except Exception as e:
            logger.error(f"Error during CyberScoutApp shutdown: {e}", exc_info=True)
