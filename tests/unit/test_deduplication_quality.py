"""
Deduplication quality, precision, recall, and false positive/negative rate tests for CyberScout AI.
"""

import unittest

from src.models.opportunity import Opportunity
from src.processors.deduplicator import DeduplicatorProcessor


class TestDeduplicationQuality(unittest.TestCase):
    def setUp(self):
        self.dedup = DeduplicatorProcessor()

    def test_exact_duplicate_detection(self):
        """Verify exact URL duplicates are caught with 100% precision."""
        opp1 = Opportunity(
            title="Senior Penetration Tester",
            url="https://example.com/jobs/101",
            source_id="linkedin",
            category="job",
        )
        opp2 = Opportunity(
            title="Senior Penetration Tester (Repost)",
            url="https://example.com/jobs/101",
            source_id="indeed",
            category="job",
        )

        res1 = self.dedup.process(opp1)
        res2 = self.dedup.process(opp2)

        self.assertIsNotNone(res1)
        self.assertIsNone(res2)  # Second item should be rejected as duplicate

    def test_unique_items_pass(self):
        """Verify distinct URLs pass without false positives."""
        opp1 = Opportunity(
            title="SANS Cyber Summit 2026",
            url="https://example.com/event/1",
            source_id="sans",
            category="event",
        )
        opp2 = Opportunity(
            title="DEFCON 34 Call for Papers",
            url="https://example.com/event/2",
            source_id="defcon",
            category="event",
        )

        res1 = self.dedup.process(opp1)
        res2 = self.dedup.process(opp2)

        self.assertIsNotNone(res1)
        self.assertIsNotNone(res2)

    def test_deduplication_quality_metrics(self):
        """Calculate precision and recall over a synthetic dataset of duplicates vs unique items."""
        dataset = [
            # 5 unique items
            Opportunity(title=f"Unique Item {i}", url=f"https://unique.org/item/{i}", source_id="src1")
            for i in range(5)
        ]
        # Add 5 duplicates of item 0
        for i in range(5):
            dataset.append(Opportunity(title="Unique Item 0", url="https://unique.org/item/0", source_id="src2"))

        # Ground truth: 5 unique items should pass, 5 duplicates should be rejected
        passed = 0
        rejected = 0

        for item in dataset:
            res = self.dedup.process(item)
            if res is not None:
                passed += 1
            else:
                rejected += 1

        self.assertEqual(passed, 5)
        self.assertEqual(rejected, 5)


if __name__ == "__main__":
    unittest.main()
