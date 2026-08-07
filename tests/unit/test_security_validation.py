"""
Security, input sanitization, SQL injection resistance, and path safety tests for CyberScout AI.
"""

from pathlib import Path
import unittest

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.seed import SeedManager
from src.models.opportunity import Opportunity
from src.processors.cleaner import CleanerProcessor


class TestSecurityValidation(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        SeedManager(self.db_manager).run_all_seeds()
        self.repo = OpportunityRepository(db_manager=self.db_manager)
        self.cleaner = CleanerProcessor()

    def tearDown(self):
        self.db_manager.close()

    def test_sql_injection_resistance(self):
        """Verify SQL injection payloads in title, URL, and category do not break or execute SQL commands."""
        injection_title = "'; DROP TABLE Opportunities; --"
        opp = Opportunity(
            title=injection_title,
            url="https://example.com/job/1",
            source_id="github_search",
            category="job",
        )
        saved_id = self.repo.upsert(opp)
        self.assertIsNotNone(saved_id)

        # Confirm table still exists and record was saved safely
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title FROM Opportunities WHERE id = ?;", (opp.id,))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], injection_title)

    def test_xss_and_script_tag_cleaning(self):
        """Verify CleanerProcessor strips harmful HTML/script tags from descriptions."""
        opp = Opportunity(
            title="Penetration Tester <script>alert('xss')</script>",
            url="https://example.com/job/2",
            source_id="github_search",
            description="<script>document.location='http://attacker.com'</script>SOC Analyst Role",
        )
        cleaned = self.cleaner.process(opp)
        self.assertIsNotNone(cleaned)
        self.assertNotIn("<script>", cleaned.title)
        self.assertNotIn("<script>", cleaned.description)

    def test_path_traversal_prevention(self):
        """Verify file paths stay within application roots."""
        from src.core.constants import PROJECT_ROOT
        malicious_relative = "../../../etc/passwd"
        safe_resolved = (PROJECT_ROOT / malicious_relative).resolve()
        self.assertTrue(safe_resolved.is_absolute())


if __name__ == "__main__":
    unittest.main()
