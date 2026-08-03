"""
Unit tests for template presence and syntax checking.
"""

import unittest

from src.notifier.template_loader import TemplateLoader


class TestTemplates(unittest.TestCase):
    def test_load_all_required_templates(self):
        loader = TemplateLoader()

        report_template = loader.load_template("report.html")
        self.assertIsNotNone(report_template)

        base_template = loader.load_template("base.html")
        self.assertIsNotNone(base_template)

        header_template = loader.load_template("header.html")
        self.assertIsNotNone(header_template)

        footer_template = loader.load_template("footer.html")
        self.assertIsNotNone(footer_template)


if __name__ == "__main__":
    unittest.main()
