"""
Deadline Urgency Engine for CyberScout AI.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger
from src.utils.date_utils import parse_iso_date

logger = get_logger(__name__)


class DeadlineEngine:
    """
    Calculates deadline status and days remaining.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "deadline_rules.yaml")
        self.urgent_days = 3
        self.upcoming_days = 14
        self.long_term_days = 30
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads deadline window rules from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                windows = data.get("windows", {})
                self.urgent_days = int(windows.get("urgent_days", 3))
                self.upcoming_days = int(windows.get("upcoming_days", 14))
                self.long_term_days = int(windows.get("long_term_days", 30))
            except Exception as e:
                logger.warning(f"Could not load deadline_rules.yaml: {e}")

    def evaluate_deadline(self, deadline_str: Optional[str]) -> Tuple[str, Optional[int]]:
        """
        Evaluates deadline status and days remaining.

        Args:
            deadline_str: Target deadline date string.

        Returns:
            Tuple of (status_string, days_remaining_or_None).
        """
        if not deadline_str:
            return "NO_DEADLINE", None

        dt = parse_iso_date(deadline_str)
        if not dt:
            return "NO_DEADLINE", None

        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        days_remaining = (dt - now).days

        if days_remaining < 0:
            return "EXPIRED", days_remaining
        if days_remaining <= self.urgent_days:
            return "URGENT", days_remaining
        if days_remaining <= self.upcoming_days:
            return "UPCOMING", days_remaining

        return "LONG_TERM", days_remaining
