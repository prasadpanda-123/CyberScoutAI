"""
Collector Registry for CyberScout AI Collection Framework.
"""

from pathlib import Path
from typing import Dict, List, Optional, Type
import yaml

from src.collectors.base import BaseCollector
from src.core.constants import CONFIG_DIR
from src.core.exceptions import CollectorError
from src.core.logging import get_logger

logger = get_logger(__name__)


class CollectorRegistry:
    """
    Central registry for discovering and registering collector implementations.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "collectors.yaml")
        self._registry: Dict[str, Type[BaseCollector]] = {}
        self._auto_register_default_collectors()
        self.load_configuration()

    def _auto_register_default_collectors(self) -> None:
        """Auto-registers core framework collector classes."""
        try:
            from src.collectors.rss_collector import GenericRSSCollector
            from src.collectors.github_collector import GithubSearchCollector
            from src.collectors.youtube_collector import YouTubeRSSCollector
            from src.collectors.ctftime_collector import CtftimeCollector

            for cls in [GenericRSSCollector, GithubSearchCollector, YouTubeRSSCollector, CtftimeCollector]:
                self.register(cls)
        except Exception as e:
            logger.warning(f"Auto-registration of core collectors failed: {e}")

    def load_configuration(self) -> None:
        """Loads collector declarations from YAML configuration file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                logger.info(f"CollectorRegistry loaded config from '{self.config_file}'.")
            except Exception as e:
                logger.warning(f"Could not load collectors.yaml: {e}")

    def register(self, collector_class: Type[BaseCollector]) -> None:
        """
        Registers a BaseCollector subclass.

        Args:
            collector_class: Class inheriting from BaseCollector.
        """
        if not issubclass(collector_class, BaseCollector):
            raise CollectorError(f"Target class '{collector_class.__name__}' must inherit from BaseCollector.")
        name = collector_class.__name__
        self._registry[name] = collector_class
        logger.info(f"Registered collector class '{name}'.")

    def get_collector_class(self, class_name: str) -> Optional[Type[BaseCollector]]:
        """Retrieves collector class by name."""
        return self._registry.get(class_name)

    def list_collectors(self) -> List[str]:
        """Returns list of registered collector class names."""
        return list(self._registry.keys())
