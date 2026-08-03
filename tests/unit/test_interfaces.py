"""
Unit tests verifying abstract interface contracts (Phase 1.2).
"""

import unittest

from src.collectors.base import BaseCollector
from src.database.interfaces import IOpportunityRepository
from src.processors.base import BaseProcessor, ICleaner
from src.services.interfaces import ICollectorService


class TestInterfaces(unittest.TestCase):
    def test_abstract_class_instantiation_fails(self):
        """Verifies that direct instantiation of ABC interfaces raises TypeError."""
        with self.assertRaises(TypeError):
            BaseCollector()

        with self.assertRaises(TypeError):
            BaseProcessor()

        with self.assertRaises(TypeError):
            ICleaner()

        with self.assertRaises(TypeError):
            IOpportunityRepository()

        with self.assertRaises(TypeError):
            ICollectorService()


if __name__ == "__main__":
    unittest.main()
