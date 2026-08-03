"""
Unit tests for Phase 1.1 Project Foundation components.
"""

from pathlib import Path
import tempfile
import unittest

from src.core.config import Config
from src.core.constants import APP_NAME, PROJECT_ROOT
from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity
from src.utils.date_utils import get_utc_now, parse_iso_date
from src.utils.file_utils import read_json_file, write_json_file
from src.utils.path_utils import is_safe_path
from src.utils.string_utils import clean_text, truncate_string
from src.utils.validation_utils import is_valid_email, is_valid_url, is_valid_uuid


class TestConstants(unittest.TestCase):
    def test_constants_defined(self):
        self.assertEqual(APP_NAME, "CyberScout AI")
        self.assertTrue(PROJECT_ROOT.exists())


class TestEnums(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(str(OpportunityCategory.INTERNSHIP), "internship")
        self.assertEqual(str(Status.ACTIVE), "active")


class TestOpportunityModel(unittest.TestCase):
    def test_opportunity_creation_and_serialization(self):
        opp = Opportunity(
            title="PicoCTF 2026",
            url="https://picoctf.org",
            source_id="ctftime",
            category=OpportunityCategory.HACKATHON.value,
        )
        self.assertTrue(is_valid_uuid(opp.id))
        self.assertEqual(opp.title, "PicoCTF 2026")
        self.assertEqual(len(opp.generate_url_hash()), 64)

        data = opp.to_dict()
        self.assertEqual(data["title"], "PicoCTF 2026")
        restored = Opportunity.from_dict(data)
        self.assertEqual(restored.id, opp.id)


class TestConfig(unittest.TestCase):
    def test_config_get(self):
        cfg = Config()
        self.assertIsNotNone(cfg.get("app_env"))
        self.assertIsNotNone(cfg.get("database.name"))

    def test_config_dot_notation(self):
        cfg = Config()
        level = cfg.get("logging.level")
        self.assertIn(level, ["DEBUG", "INFO", "WARNING", "ERROR"])


class TestUtilities(unittest.TestCase):
    def test_string_utils(self):
        html = "<p>Hello <b>World</b></p>"
        self.assertEqual(clean_text(html), "Hello World")
        self.assertEqual(truncate_string("Short string", max_length=50), "Short string")
        self.assertTrue(truncate_string("Long text string test", max_length=10).endswith("..."))

    def test_validation_utils(self):
        self.assertTrue(is_valid_url("https://example.com/test"))
        self.assertFalse(is_valid_url("invalid-url"))
        self.assertTrue(is_valid_email("test@cyberscout.ai"))
        self.assertFalse(is_valid_email("invalid-email"))

    def test_date_utils(self):
        now = get_utc_now()
        self.assertIsNotNone(now)
        parsed = parse_iso_date("2026-08-03")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)

    def test_file_and_path_utils(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "test.json"
            data = {"key": "val"}
            write_json_file(tmp_path, data)
            self.assertTrue(tmp_path.exists())
            read_back = read_json_file(tmp_path)
            self.assertEqual(read_back["key"], "val")
            self.assertTrue(is_safe_path(tmp_path, base_dir=Path(tmpdir)))


if __name__ == "__main__":
    unittest.main()
