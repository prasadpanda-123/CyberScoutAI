"""
Provider Reputation Engine for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class ProviderEngine:
    """
    Evaluates provider reputation bonuses from config/provider_scores.yaml.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "provider_scores.yaml")
        self.provider_scores: Dict[str, int] = {
            "cisa": 25,
            "owasp": 25,
            "sans institute": 25,
            "mitre": 25,
            "google": 20,
            "microsoft": 20,
            "aws": 20,
            "cisco": 20,
            "tryhackme": 15,
            "hack the box": 15,
            "portswigger": 15,
            "github": 10,
        }
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads provider scores configuration from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                scores = data.get("providers", {})
                if isinstance(scores, dict):
                    for p, score in scores.items():
                        self.provider_scores[p.lower().strip()] = int(score)
            except Exception as e:
                logger.warning(f"Could not load provider_scores.yaml: {e}")

    def get_provider_bonus(self, provider_name: Optional[str]) -> int:
        """
        Calculates provider bonus score.

        Args:
            provider_name: Target provider string.

        Returns:
            Bonus score int (e.g. +25 for CISA/OWASP/SANS).
        """
        if not provider_name:
            return 0
        p_clean = provider_name.lower().strip()
        return self.provider_scores.get(p_clean, 0)
