"""
Source Capabilities Registry for CyberScout AI Search Intelligence Layer.

Loads source_capabilities.yaml and sources.yaml to track source features,
rate limits, supported categories, and preferred collector implementations.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.exceptions import IntelligenceError
from src.core.logging import get_logger

logger = get_logger(__name__)


class SourceRegistry:
    """
    Registry describing supported sources and their collection capabilities.
    """

    def __init__(
        self,
        capabilities_file: Optional[Path] = None,
        sources_file: Optional[Path] = None,
    ):
        self.capabilities_file = capabilities_file or (CONFIG_DIR / "source_capabilities.yaml")
        self.sources_file = sources_file or (CONFIG_DIR / "sources.yaml")
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.load_registry()

    def load_registry(self) -> None:
        """Loads source capabilities and merges with sources configuration."""
        if self.capabilities_file.exists():
            try:
                with open(self.capabilities_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    raw_sources = data.get("sources", data)
                    if isinstance(raw_sources, dict):
                        self.sources = raw_sources
            except Exception as e:
                raise IntelligenceError(f"Failed to load source capabilities YAML: {e}", original_exception=e)

        # Merge additional properties from sources.yaml if present
        if self.sources_file.exists():
            try:
                with open(self.sources_file, "r", encoding="utf-8") as f:
                    s_data = yaml.safe_load(f) or {}
                    s_list = s_data.get("sources", s_data)
                    if isinstance(s_list, list):
                        for item in s_list:
                            if isinstance(item, dict) and "id" in item:
                                sid = item["id"]
                                if sid not in self.sources:
                                    self.sources[sid] = {}
                                self.sources[sid].update(item)
                    elif isinstance(s_list, dict):
                        for sid, sinfo in s_list.items():
                            if sid not in self.sources:
                                self.sources[sid] = {}
                            if isinstance(sinfo, dict):
                                self.sources[sid].update(sinfo)
            except Exception as e:
                logger.warning(f"Could not merge sources.yaml: {e}")

        logger.info(f"SourceRegistry initialized with {len(self.sources)} sources.")

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves capabilities dictionary for a specific source."""
        return self.sources.get(source_id.lower().strip())

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Returns list of all registered source dictionaries."""
        return [{"id": k, **v} for k, v in self.sources.items()]

    def get_sources_for_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Retrieves active sources that support a target opportunity category.

        Args:
            category: Opportunity category string (e.g. 'ctf', 'internship').

        Returns:
            List of matching source dictionaries.
        """
        category_clean = category.lower().strip()
        matching = []

        for sid, sinfo in self.sources.items():
            supported_cats = sinfo.get("supported_categories", [])
            default_cat = sinfo.get("default_category", "")
            enabled = sinfo.get("enabled", True)

            if not enabled:
                continue

            if category_clean in [c.lower() for c in supported_cats] or category_clean == default_cat.lower():
                matching.append({"id": sid, **sinfo})

        return matching

    def get_sources_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """
        Retrieves sources supporting a specific capability flag.

        Args:
            capability: Flag name (e.g., 'supports_search', 'supports_api', 'supports_rss').

        Returns:
            List of source dictionaries where capability is True.
        """
        matching = []
        for sid, sinfo in self.sources.items():
            if sinfo.get(capability, False) and sinfo.get("enabled", True):
                matching.append({"id": sid, **sinfo})
        return matching
