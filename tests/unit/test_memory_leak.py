"""
Memory leak, garbage collection, and resource exhaustion tests for CyberScout AI.
"""

import gc
from pathlib import Path
import unittest

from src.database.connection import DatabaseManager
from src.models.opportunity import Opportunity
from src.processors.pipeline import ProcessingPipeline


class TestMemoryLeak(unittest.TestCase):
    def test_opportunity_instantiation_memory_stability(self):
        """Verify allocating and processing hundreds of Opportunity objects does not leak memory."""
        gc.collect()
        initial_objects = len(gc.get_objects())

        pipeline = ProcessingPipeline()

        # Generate and process 200 opportunities
        for i in range(200):
            opp = Opportunity(
                title=f"Security Analyst {i}",
                url=f"https://jobboard.com/job/{i}",
                source_id="jobboard",
                category="job",
                description="Looking for SOC analyst with 2 years experience.",
            )
            processed = pipeline.process_item(opp)

        gc.collect()
        final_objects = len(gc.get_objects())

        # Ensure no unbounded object growth
        object_growth = final_objects - initial_objects
        self.assertLess(object_growth, 5000, f"Excessive object leakage detected: {object_growth} new objects")

    def test_database_connection_cleanup(self):
        """Verify database connections open and close cleanly without handle leaks."""
        for _ in range(20):
            db = DatabaseManager()
            db.initialize_database()
            self.assertTrue(db.ping())
            db.close()


if __name__ == "__main__":
    unittest.main()
