"""
Configuration & Source Validation Framework for CyberScout AI.

Audits YAML files, provider definitions, collector mappings, URL syntax,
and capability matrices to enforce zero-defect runtime operation.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.collectors.registry import CollectorRegistry
from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger
from src.utils.url_utils import is_valid_url, sanitize_url

logger = get_logger(__name__)

VALID_CATEGORIES = {
    "internship", "job", "course", "certification", "scholarship",
    "hackathon", "ctf", "webinar", "news", "security_news",
    "github_repository", "security_tool", "research_paper", "tutorial", "blog", "other"
}

VALID_PRIORITIES = {"P0", "P1", "P2", "P3", 1, 2, 3, 4, 1.0, 2.0, 3.0, 4.0}


@dataclass
class ConfigIssue:
    """Represents a configuration error or warning item."""
    file_name: str
    issue_type: str  # 'ERROR' | 'WARNING'
    message: str
    field_name: Optional[str] = None
    recommended_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConfigValidationReport:
    """Master validation report across all configuration files and providers."""
    total_files: int = 0
    total_sources: int = 0
    issues: List[ConfigIssue] = field(default_factory=list)
    is_valid: bool = True

    def add_error(self, file_name: str, message: str, field_name: Optional[str] = None, fix: Optional[str] = None) -> None:
        self.issues.append(ConfigIssue(file_name=file_name, issue_type="ERROR", message=message, field_name=field_name, recommended_fix=fix))
        self.is_valid = False

    def add_warning(self, file_name: str, message: str, field_name: Optional[str] = None, fix: Optional[str] = None) -> None:
        self.issues.append(ConfigIssue(file_name=file_name, issue_type="WARNING", message=message, field_name=field_name, recommended_fix=fix))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_sources": self.total_sources,
            "is_valid": self.is_valid,
            "error_count": sum(1 for i in self.issues if i.issue_type == "ERROR"),
            "warning_count": sum(1 for i in self.issues if i.issue_type == "WARNING"),
            "issues": [i.to_dict() for i in self.issues],
        }


class ConfigurationValidator:
    """
    Validates YAML configurations, sources, collector mappings, and URL syntax.
    """

    def __init__(self, config_dir: Optional[Path] = None, registry: Optional[CollectorRegistry] = None):
        self.config_dir = config_dir or CONFIG_DIR
        self.registry = registry or CollectorRegistry()

    def validate_all(self) -> ConfigValidationReport:
        """
        Executes master configuration audit across all YAML files in config/.

        Returns:
            ConfigValidationReport object.
        """
        report = ConfigValidationReport()

        if not self.config_dir.exists():
            report.add_error("config/", f"Config directory '{self.config_dir}' does not exist.")
            return report

        yaml_files = list(self.config_dir.glob("*.yaml"))
        report.total_files = len(yaml_files)

        registered_collectors = set(self.registry.list_collectors())

        # 1. Audit each YAML syntax and structure
        for yf in yaml_files:
            file_name = yf.name
            try:
                with open(yf, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data is None:
                    report.add_warning(file_name, "YAML file is empty.", fix="Add configuration key-value declarations.")
            except Exception as e:
                report.add_error(file_name, f"Invalid YAML syntax: {e}", fix="Fix YAML formatting syntax error.")

        # 2. Audit sources.yaml
        sources_file = self.config_dir / "sources.yaml"
        if sources_file.exists():
            self._validate_sources_file(sources_file, registered_collectors, report)

        # 3. Audit collectors.yaml
        collectors_file = self.config_dir / "collectors.yaml"
        if collectors_file.exists():
            self._validate_collectors_file(collectors_file, registered_collectors, report)

        # 4. Audit source_capabilities.yaml
        cap_file = self.config_dir / "source_capabilities.yaml"
        if cap_file.exists():
            self._validate_capabilities_file(cap_file, registered_collectors, report)

        return report

    def _validate_sources_file(self, file_path: Path, registered_collectors: set, report: ConfigValidationReport) -> None:
        """Validates sources.yaml source definitions."""
        file_name = file_path.name
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            sources = data.get("sources", [])
            if not isinstance(sources, list):
                report.add_error(file_name, "'sources' key must contain a list of source objects.")
                return

            report.total_sources = len(sources)
            seen_ids = set()

            for idx, src in enumerate(sources):
                if not isinstance(src, dict):
                    report.add_error(file_name, f"Source at index {idx} is not a valid dictionary object.")
                    continue

                sid = src.get("id")
                if not sid:
                    report.add_error(file_name, f"Source at index {idx} missing mandatory 'id' field.")
                    continue

                if sid in seen_ids:
                    report.add_error(file_name, f"Duplicate source ID '{sid}' found.", field_name="id", fix="Use unique source IDs.")
                seen_ids.add(sid)

                # Validate URL syntax if base_url exists
                base_url = src.get("base_url")
                if base_url and "REPLACE_WITH_CHANNEL_ID" not in base_url:
                    try:
                        sanitize_url(base_url)
                    except Exception as ve:
                        report.add_error(file_name, f"Source '{sid}' has invalid base_url '{base_url}': {ve}", field_name="base_url", fix="Fix URL hostname or scheme.")

                # Validate default_category
                cat = src.get("default_category")
                if cat and cat not in VALID_CATEGORIES:
                    report.add_warning(file_name, f"Source '{sid}' uses non-standard category '{cat}'.", field_name="default_category")

                # Validate priority
                prio = src.get("priority")
                if prio and prio not in VALID_PRIORITIES:
                    report.add_warning(file_name, f"Source '{sid}' has non-standard priority '{prio}'.", field_name="priority")

        except Exception as e:
            report.add_error(file_name, f"Failed to parse sources.yaml: {e}")

    def _validate_collectors_file(self, file_path: Path, registered_collectors: set, report: ConfigValidationReport) -> None:
        """Validates collectors.yaml collector declarations."""
        file_name = file_path.name
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            collectors = data.get("collectors", {})
            for c_name, c_info in collectors.items():
                if c_name == "GenericCollector":
                    report.add_error(file_name, "Legacy 'GenericCollector' referenced in collectors.yaml.", fix="Replace with 'GenericRSSCollector'.")
                elif c_name not in registered_collectors:
                    report.add_warning(file_name, f"Collector '{c_name}' declared in YAML but not registered in CollectorRegistry.", fix="Register collector class in registry.py.")
        except Exception as e:
            report.add_error(file_name, f"Failed to parse collectors.yaml: {e}")

    def _validate_capabilities_file(self, file_path: Path, registered_collectors: set, report: ConfigValidationReport) -> None:
        """Validates source_capabilities.yaml mapping."""
        file_name = file_path.name
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            sources = data.get("sources", {})
            for sid, cap in sources.items():
                pref = cap.get("preferred_collector")
                if pref == "GenericCollector":
                    report.add_error(file_name, f"Source '{sid}' specifies legacy 'GenericCollector'.", fix="Change preferred_collector to 'GenericRSSCollector'.")
                elif pref and pref not in registered_collectors:
                    report.add_warning(file_name, f"Source '{sid}' specifies unregistered collector '{pref}'.")
        except Exception as e:
            report.add_error(file_name, f"Failed to parse source_capabilities.yaml: {e}")
