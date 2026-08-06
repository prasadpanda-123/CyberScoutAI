"""
Configuration loader for the CyberScout AI application.

Loads configuration from YAML files and environment variables, providing
strongly-typed, dot-notation access to project settings.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv

from src.core.constants import (
    CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    KEYWORDS_CONFIG_FILE,
    PROJECT_ROOT,
    SCHEDULE_CONFIG_FILE,
    SOURCES_CONFIG_FILE,
    WEIGHTS_CONFIG_FILE,
)
from src.core.exceptions import ConfigurationError


class Config:
    """
    Centralized configuration management class.
    Reads YAML files in config/ and environment variables (.env).
    """

    def __init__(self, config_files: Optional[List[Path]] = None):
        self._config: Dict[str, Any] = {}
        self._load_environment_variables()
        self._load_config_files(config_files)
        self._apply_env_overrides()
        self._validate_config()

    def _load_environment_variables(self) -> None:
        """Loads environment variables from .env file if it exists."""
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)

    def _load_config_files(self, config_files: Optional[List[Path]]) -> None:
        """Loads and merges configuration YAML files."""
        if config_files is None:
            # Default pipeline of configuration files
            config_files = [DEFAULT_CONFIG_FILE]
            # Load supplementary domain configs if present
            for extra_file in [SOURCES_CONFIG_FILE, KEYWORDS_CONFIG_FILE, SCHEDULE_CONFIG_FILE, WEIGHTS_CONFIG_FILE]:
                if extra_file.exists():
                    config_files.append(extra_file)

        for cfg_file in config_files:
            if not cfg_file.exists():
                raise ConfigurationError(f"Configuration file not found: {cfg_file}")
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                    if isinstance(content, dict):
                        # Merge domain key if file name matches domain
                        domain_key = cfg_file.stem
                        if domain_key != "settings":
                            self._config[domain_key] = content
                        else:
                            self._merge_dicts(self._config, content)
            except yaml.YAMLError as e:
                raise ConfigurationError(f"YAML parsing error in {cfg_file}: {e}", original_exception=e)
            except Exception as e:
                raise ConfigurationError(f"Failed to read {cfg_file}: {e}", original_exception=e)

    def _merge_dicts(self, base: Dict[str, Any], incoming: Dict[str, Any]) -> None:
        """Recursively merges dictionary incoming into base."""
        for key, value in incoming.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    def _apply_env_overrides(self) -> None:
        """Overrides configuration settings with environment variables."""
        env_mappings = {
            "APP_ENV": "app_env",
            "LOG_LEVEL": "logging.level",
            "LOG_FILE": "logging.file",
            "DATABASE_URL": "database.url",
        }
        for env_var, config_path in env_mappings.items():
            val = os.getenv(env_var)
            if val is not None:
                self.set(config_path, self._cast_val(val))

    def _cast_val(self, val: str) -> Any:
        """Casts string environment variable to primitive type."""
        if val.lower() in ("true", "1"):
            return True
        if val.lower() in ("false", "0"):
            return False
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def _validate_config(self) -> None:
        """Validates presence of essential config sections and values."""
        required = [
            ("app_env", str),
            ("logging.level", str),
        ]
        for key, expected_type in required:
            val = self.get(key)
            if val is None:
                raise ConfigurationError(f"Missing required configuration key: '{key}'")
            if not isinstance(val, expected_type):
                raise ConfigurationError(
                    f"Configuration key '{key}' must be of type {expected_type.__name__}, got {type(val).__name__}"
                )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value using dot notation (e.g., 'logging.level').

        Args:
            key: Dot-separated string key.
            default: Fallback value if key is not found.

        Returns:
            The setting value or default.
        """
        parts = key.split(".")
        curr = self._config
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return default
        return curr

    def set(self, key: str, value: Any) -> None:
        """Sets a configuration value using dot notation."""
        parts = key.split(".")
        curr = self._config
        for p in parts[:-1]:
            if p not in curr or not isinstance(curr[p], dict):
                curr[p] = {}
            curr = curr[p]
        curr[parts[-1]] = value

    def as_dict(self) -> Dict[str, Any]:
        """Returns dictionary representation of current loaded config."""
        return self._config.copy()

    def to_dict(self) -> Dict[str, Any]:
        """Returns dictionary representation of current loaded config."""
        return self._config.copy()

    @property
    def raw_config(self) -> Dict[str, Any]:
        """Returns read-only view of current loaded config dictionary."""
        return self._config.copy()


# Global singleton instance
config = Config()
