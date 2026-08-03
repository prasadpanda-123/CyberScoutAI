"""
Weight Manager for CyberScout AI Intelligence Layer.
"""

from pathlib import Path
from typing import Dict, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class WeightManager:
    """
    Manages declarative scoring weights from config/weights.yaml.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "weights.yaml")
        self.rule_weights: Dict[str, int] = {
            "is_free": 40,
            "has_certificate": 20,
            "is_remote": 20,
            "is_beginner_friendly": 15,
            "trusted_provider": 20,
            "deadline_soon": 10,
        }
        self.penalties: Dict[str, int] = {
            "is_spam": -100,
            "is_duplicate": -100,
            "is_expired": -100,
        }
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads weights configuration from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.rule_weights.update(data.get("rule_weights", {}))
                self.penalties.update(data.get("penalties", {}))
            except Exception as e:
                logger.warning(f"Could not load weights.yaml: {e}")

    def get_weight(self, rule_name: str) -> int:
        """Retrieves score weight or penalty for a rule."""
        if rule_name in self.rule_weights:
            return self.rule_weights[rule_name]
        if rule_name in self.penalties:
            return self.penalties[rule_name]
        return 0
