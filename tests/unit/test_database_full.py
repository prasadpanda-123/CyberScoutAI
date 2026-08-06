"""
Full Unit Tests for Database Infrastructure (Phase 1.3).
"""

import unittest

from src.core.exceptions import RepositoryError
from src.database.connection import DatabaseManager
from src.database.keyword_repository import KeywordRepository
from src.database.migrations import MigrationManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.seed import SeedManager
from src.database.source_repository import SourceRepository
from src.database.stats_repository import PreferencesRepository, StatisticsRepository
from src.models.opportunity import Opportunity
from src.models.source import Source
from src.models.stats import Preferences


class TestDatabaseFull(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()

        self.opp_repo = OpportunityRepository(self.db_manager)
        self.source_repo = SourceRepository(self.db_manager)
        self.kw_repo = KeywordRepository(self.db_manager)
        self.pref_repo = PreferencesRepository(self.db_manager)
        self.stats_repo = StatisticsRepository(self.db_manager)

    def tearDown(self):
        self.db_manager.close()

    def test_database_health_and_integrity(self):
        self.assertTrue(self.db_manager.ping())
        self.assertTrue(self.db_manager.verify_integrity())
        tables = self.db_manager.get_existing_tables()
        self.assertIn("Opportunities", tables)
        self.assertIn("Sources", tables)

    def test_base_repository_crud(self):
        initial_count = self.source_repo.count()
        # 1. Create Source
        src = Source(id="src-1", name="Test Source", collection_method="rss")
        created_id = self.source_repo.create(src)
        self.assertEqual(created_id, "src-1")

        # 2. Exists & Read
        self.assertTrue(self.source_repo.exists("src-1"))
        fetched = self.source_repo.read_by_id("src-1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Test Source")

        # 3. Update
        fetched.name = "Updated Source Name"
        updated = self.source_repo.update(fetched)
        self.assertTrue(updated)
        re_fetched = self.source_repo.read_by_id("src-1")
        self.assertEqual(re_fetched.name, "Updated Source Name")

        # 4. Count & Search
        self.assertEqual(self.source_repo.count(), initial_count + 1)
        search_results = self.source_repo.search(where_clause="id = ?", params=("src-1",))
        self.assertEqual(len(search_results), 1)

        # 5. Paginate
        items, total = self.source_repo.paginate(page=1, page_size=50)
        self.assertEqual(total, initial_count + 1)

        # 6. Delete
        deleted = self.source_repo.delete("src-1")
        self.assertTrue(deleted)
        self.assertFalse(self.source_repo.exists("src-1"))
        self.assertEqual(self.source_repo.count(), initial_count)

    def test_bulk_insert(self):
        import uuid
        uid = uuid.uuid4().hex[:8]
        initial_count = self.source_repo.count()
        sources = [
            Source(id=f"src-bulk-{uid}-{i}", name=f"Source {uid} {i}", collection_method="rss")
            for i in range(5)
        ]
        inserted = self.source_repo.bulk_insert(sources)
        self.assertEqual(inserted, 5)
        self.assertEqual(self.source_repo.count(), initial_count + 5)

    def test_seed_manager(self):
        seed_mgr = SeedManager(self.db_manager)
        seed_mgr.run_all_seeds()
        self.assertGreaterEqual(self.pref_repo.count(), 1)


if __name__ == "__main__":
    unittest.main()
