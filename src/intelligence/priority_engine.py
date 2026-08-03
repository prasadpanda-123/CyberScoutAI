"""
Priority Level Engine for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class PriorityEngine:
    """
    Maps final opportunity scores to priority levels (P0, P1, P2, P3).
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "priority_levels.yaml")
        self.p0_min = 80
        self.p1_min = 60
        self.p2_min = 40
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads priority level thresholds from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                levels = data.get("levels", {})
                self.p0_min = int(levels.get("P0", {}).get("min_score", 80))
                self.p1_min = int(levels.get("P1", {}).get("min_score", 60))
                self.p2_min = int(levels.get("P2", {}).get("min_score", 40))
            except Exception as e:
                logger.warning(f"Could not load priority_levels.yaml: {e}")

    def assign_priority(self, score: int) -> str:
        """
        Assigns priority level string (P0, P1, P2, P3).

        Args:
            score: Final calculated overall score.

        Returns:
            Priority level string.
        """
        if score >= self.p0_min:
            return "P0"
        if score >= self.p1_min:
            return "P1"
        if score >= self.p2_min:
            return "P2"
        return "P3"
