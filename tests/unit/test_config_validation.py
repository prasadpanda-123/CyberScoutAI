"""
Configuration schema, key integrity, and YAML validation tests for CyberScout AI.
"""

from pathlib import Path
import unittest
import yaml

from src.core.constants import CONFIG_DIR


class TestConfigValidation(unittest.TestCase):
    def test_all_yaml_files_parse_without_errors(self):
        """Verify all YAML files in config/ directory parse cleanly without syntax errors."""
        yaml_files = list(CONFIG_DIR.glob("*.yaml"))
        self.assertGreater(len(yaml_files), 0, "No YAML configuration files found!")

        for yaml_path in yaml_files:
            with self.subTest(file=yaml_path.name):
                with open(yaml_path, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                self.assertIsNotNone(content, f"Config file '{yaml_path.name}' parsed to None or empty")

    def test_settings_yaml_structure(self):
        """Verify settings.yaml contains expected core configuration keys."""
        settings_file = CONFIG_DIR / "settings.yaml"
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.assertIn("app_env", data)
            self.assertIn("database", data)

    def test_sources_yaml_structure(self):
        """Verify sources.yaml contains valid source declarations."""
        sources_file = CONFIG_DIR / "sources.yaml"
        if sources_file.exists():
            with open(sources_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.assertIn("sources", data)
            self.assertGreater(len(data["sources"]), 0)
            for src in data["sources"]:
                self.assertIn("id", src)
                self.assertIn("name", src)

    def test_scheduler_yaml_structure(self):
        """Verify scheduler.yaml configuration options."""
        sched_file = CONFIG_DIR / "scheduler.yaml"
        if sched_file.exists():
            with open(sched_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.assertIn("schedule", data)
            self.assertIn("type", data["schedule"])


if __name__ == "__main__":
    unittest.main()
