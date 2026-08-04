"""
Unit tests for CLI Command Documentation Generator.
"""

from pathlib import Path
import tempfile
import unittest

from src.main import build_parser
from src.utils.command_doc_generator import generate_all_command_docs, introspect_parser


class TestCommandDocGenerator(unittest.TestCase):
    """Tests command introspection, commands.txt, and commands.md generation."""

    def setUp(self):
        self.parser = build_parser()

    def test_introspect_parser_detects_all_actions(self):
        """Verify introspect_parser detects every registered argparse flag."""
        entries = introspect_parser(self.parser)
        self.assertGreater(len(entries), 10)

        # Check key flags exist
        long_flags = [e["long_flag"] for e in entries]
        self.assertIn("--version", long_flags)
        self.assertIn("--health", long_flags)
        self.assertIn("--config-check", long_flags)
        self.assertIn("--db-check", long_flags)
        self.assertIn("--env-status", long_flags)
        self.assertIn("--github-status", long_flags)
        self.assertIn("--run-once", long_flags)
        self.assertIn("--daemon", long_flags)
        self.assertIn("--dry-run", long_flags)
        self.assertIn("--dashboard", long_flags)
        self.assertIn("--email-test", long_flags)
        self.assertIn("--generate-command-docs", long_flags)

    def test_no_duplicate_flags_in_introspection(self):
        """Verify no duplicate long flags are produced."""
        entries = introspect_parser(self.parser)
        long_flags = [e["long_flag"] for e in entries]
        self.assertEqual(len(long_flags), len(set(long_flags)))

    def test_file_generation(self):
        """Verify generate_all_command_docs creates commands.txt and commands.md."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            txt_path, md_path = generate_all_command_docs(self.parser, root_dir=tmp_path)

            self.assertTrue(txt_path.exists())
            self.assertTrue(md_path.exists())

            txt_content = txt_path.read_text(encoding="utf-8")
            md_content = md_path.read_text(encoding="utf-8")

            # Check txt structure
            self.assertIn("CyberScout AI CLI Reference", txt_content)
            self.assertIn("python main.py --version", txt_content)
            self.assertIn("python main.py --generate-command-docs", txt_content)

            # Check md structure
            self.assertIn("# CyberScout AI — CLI Command Reference & Workflow Guide", md_content)
            self.assertIn("| Category | Command | Description |", md_content)
            self.assertIn("### 1. Fresh Installation Workflow", md_content)


if __name__ == "__main__":
    unittest.main()
