"""
Database Backup and Restore Utilities for CyberScout AI.

Provides online SQLite backups, restores, and integrity verification.
"""

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
from typing import Optional

from src.core.constants import DATA_DIR
from src.core.exceptions import DatabaseError
from src.core.logging import get_logger
from src.database.connection import DatabaseManager

logger = get_logger(__name__)


class BackupManager:
    """
    Manages SQLite database backups, restores, and integrity validation.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def backup_database(self, backup_dir: Optional[Path] = None) -> Path:
        """
        Performs an online SQLite backup using SQLite's native backup API.

        Args:
            backup_dir: Directory where backup file will be saved. Defaults to DATA_DIR/backups.

        Returns:
            Path to the created backup file.
        """
        dest_dir = backup_dir or (DATA_DIR / "backups")
        dest_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = dest_dir / f"cyberscout_backup_{timestamp}.db"

        try:
            source_conn = self.db_manager.get_connection()
            dest_conn = sqlite3.connect(str(backup_file))
            with dest_conn:
                source_conn.backup(dest_conn)
            dest_conn.close()
            logger.info(f"Database online backup created successfully at '{backup_file}'.")
            return backup_file
        except Exception as e:
            raise DatabaseError(f"Failed to create database backup: {e}", original_exception=e)

    def restore_database(self, backup_path: Path) -> bool:
        """
        Restores the SQLite database file from a target backup file.

        Args:
            backup_path: Path to valid backup SQLite file.

        Returns:
            True if restore succeeded.
        """
        if not backup_path.exists():
            raise DatabaseError(f"Backup file not found at '{backup_path}'.")

        try:
            # Close active connection before restoring file
            self.db_manager.close()
            shutil.copy2(backup_path, self.db_manager.db_path)
            # Re-open and verify restored database
            self.db_manager.initialize_database()
            valid = self.db_manager.verify_integrity()
            if valid:
                logger.info(f"Database successfully restored from '{backup_path}'.")
                return True
            else:
                raise DatabaseError("Restored database failed integrity check.")
        except Exception as e:
            raise DatabaseError(f"Failed to restore database from '{backup_path}': {e}", original_exception=e)

    def verify_integrity(self) -> bool:
        """Runs PRAGMA quick_check to verify database file health."""
        return self.db_manager.verify_integrity()
