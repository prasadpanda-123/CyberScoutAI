"""
Provider Normalization Helper for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, Optional
import yaml

from src.core.constants import CONFIG_DIR


def normalize_provider_name(provider_raw: Optional[str], config_file: Optional[Path] = None) -> str:
    """
    Normalizes raw provider string using config/providers.yaml mappings.

    Args:
        provider_raw: Raw provider string.
        config_file: Optional providers.yaml path.

    Returns:
        Canonical provider string.
    """
    if not provider_raw or not provider_raw.strip():
        return "Unknown"

    raw_clean = provider_raw.strip().lower()
    cfg_path = config_file or (CONFIG_DIR / "providers.yaml")

    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                providers_map = data.get("providers", {})
                if raw_clean in providers_map:
                    return providers_map[raw_clean]
        except Exception:
            pass

    return provider_raw.strip().capitalize()
