"""
Retention Policy Manager for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.database.archive import ArchiveManager
from src.database.connection import DatabaseManager


class RetentionPolicyManager:
    """
    Executes automated retention policies and database cleanup routines.
    """

    def __init__(
        self,
        config_file: Optional[Path] = None,
        db_manager: Optional[DatabaseManager] = None,
        archive_manager: Optional[ArchiveManager] = None,
    ):
        self.config_file = config_file or (CONFIG_DIR / "retention.yaml")
        self.db_manager = db_manager or DatabaseManager()
        self.archive_manager = archive_manager or ArchiveManager(db_manager=self.db_manager)
        self.archive_expired_days = 90
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads retention settings from YAML configuration file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.archive_expired_days = int(data.get("archive_expired_days", 90))
            except Exception:
                pass

    def run_retention_policy(self) -> Dict[str, int]:
        """
        Executes retention policy cleanup.

        Returns:
            Dictionary mapping task_name -> affected_records_count.
        """
        archived_cnt = self.archive_manager.archive_expired_opportunities(self.archive_expired_days)
        return {
            "archived_opportunities": archived_cnt,
        }
