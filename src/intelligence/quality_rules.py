"""
Quality Rules and Configuration Loader for CyberScout AI.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class QualityRules:
    """
    Manages configurable thresholds, approved topics, approved programming languages,
    blacklist terms, and quality weightings.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (CONFIG_DIR / "quality.yaml")

        self.minimum_confidence: float = 60.0
        self.minimum_keyword_score: float = 20.0
        self.minimum_topic_score: float = 15.0
        self.spam_threshold: float = 0.70
        self.duplicate_threshold: float = 0.85
        self.max_readme_urls: int = 200

        self.weights: Dict[str, float] = {
            "keyword_weight": 0.35,
            "topic_weight": 0.25,
            "language_weight": 0.15,
            "relevance_weight": 0.15,
            "source_credibility_weight": 0.10,
        }

        self.approved_topics: List[str] = []
        self.approved_languages: List[str] = []
        self.penalized_languages: List[str] = []
        self.blacklist_keywords: List[str] = []
        self.preferred_keywords: List[str] = []

        self.load_rules()

    def load_rules(self) -> None:
        """Loads quality settings from config/quality.yaml."""
        if not self.config_path.exists():
            logger.warning(f"Quality rules config file '{self.config_path}' not found. Using defaults.")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            thresh = data.get("thresholds", {})
            self.minimum_confidence = float(thresh.get("minimum_confidence", self.minimum_confidence))
            self.minimum_keyword_score = float(thresh.get("minimum_keyword_score", self.minimum_keyword_score))
            self.minimum_topic_score = float(thresh.get("minimum_topic_score", self.minimum_topic_score))
            self.spam_threshold = float(thresh.get("spam_threshold", self.spam_threshold))
            self.duplicate_threshold = float(thresh.get("duplicate_threshold", self.duplicate_threshold))
            self.max_readme_urls = int(thresh.get("max_readme_urls", self.max_readme_urls))

            if "quality_weights" in data:
                self.weights.update(data["quality_weights"])

            self.approved_topics = [t.lower().strip() for t in data.get("approved_topics", [])]
            self.approved_languages = [l.lower().strip() for l in data.get("approved_languages", [])]
            self.penalized_languages = [l.lower().strip() for l in data.get("penalized_languages", [])]
            self.blacklist_keywords = [k.lower().strip() for k in data.get("blacklist_keywords", [])]
            self.preferred_keywords = [k.lower().strip() for k in data.get("preferred_keywords", [])]

            logger.info(f"QualityRules loaded successfully from '{self.config_path.name}'.")
        except Exception as e:
            logger.error(f"Error loading quality rules: {e}")
