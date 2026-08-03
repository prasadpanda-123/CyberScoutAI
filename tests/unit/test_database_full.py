"""
Full Unit Tests for Database Infrastructure (Phase 1.3).
"""

from pathlib import Path
import tempfile
import unittest

from src.core.exceptions import DatabaseError, IntegrityError, RepositoryError
from src.database.backup import BackupManager
from src.database.connection import DatabaseManager
from src.database.keyword_repository import KeywordRepository
from src.database.migrations import MigrationManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.seed import SeedManager
from src.database.source_repository import SourceRepository
from src.database.stats_repository import PreferencesRepository, StatisticsRepository
from src.models.enums import OpportunityCategory, Status
from src.models.keyword import Keyword
from src.models.opportunity import Opportunity
from src.models.source import Source
from src.models.stats import ApplicationStatistics, Preferences


class TestDatabaseFull(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_full.db"
        self.db_manager = DatabaseManager(db_path=self.db_path)
        self.db_manager.initialize_database()

        self.opp_repo = OpportunityRepository(self.db_manager)
        self.source_repo = SourceRepository(self.db_manager)
        self.kw_repo = KeywordRepository(self.db_manager)
        self.pref_repo = PreferencesRepository(self.db_manager)
        self.stats_repo = StatisticsRepository(self.db_manager)

    def tearDown(self):
        self.db_manager.close()
        self.temp_dir.cleanup()

    def test_database_health_and_integrity(self):
        self.assertTrue(self.db_manager.ping())
        self.assertTrue(self.db_manager.verify_integrity())
        tables = self.db_manager.get_existing_tables()
        self.assertIn("Opportunities", tables)
        self.assertIn("Sources", tables)
        self.assertIn("schema_version", tables)

    def test_base_repository_crud(self):
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
        self.assertEqual(self.source_repo.count(), 1)
        search_results = self.source_repo.search(where_clause="collection_method = ?", params=("rss",))
        self.assertEqual(len(search_results), 1)

        # 5. Paginate
        items, total = self.source_repo.paginate(page=1, page_size=10)
        self.assertEqual(total, 1)
        self.assertEqual(len(items), 1)

        # 6. Delete
        deleted = self.source_repo.delete("src-1")
        self.assertTrue(deleted)
        self.assertFalse(self.source_repo.exists("src-1"))

    def test_bulk_insert(self):
        sources = [
            Source(id=f"src-{i}", name=f"Source {i}", collection_method="rss")
            for i in range(5)
        ]
        inserted = self.source_repo.bulk_insert(sources)
        self.assertEqual(inserted, 5)
        self.assertEqual(self.source_repo.count(), 5)

    def test_transaction_rollback_safety(self):
        # FK Constraint violation should rollback transaction cleanly
        opp_without_source = Opportunity(
            id="opp-fk-fail",
            title="Invalid FK Opp",
            url="https://example.com/fk",
            source_id="non-existent-source",
        )
        with self.assertRaises((IntegrityError, RepositoryError)):
            self.opp_repo.create(opp_without_source)

        self.assertFalse(self.opp_repo.exists("opp-fk-fail"))

    def test_migration_manager(self):
        mig_mgr = MigrationManager(self.db_manager)
        applied = mig_mgr.apply_migrations()
        # Migration v1 is baseline
        self.assertGreaterEqual(mig_mgr.get_current_version(), 1)

    def test_seed_manager(self):
        seed_mgr = SeedManager(self.db_manager)
        seed_mgr.run_all_seeds()
        self.assertGreaterEqual(self.pref_repo.count(), 1)

    def test_backup_and_restore(self):
        # Insert test data
        pref = Preferences(key="backup_test_key", value="backup_test_val")
        self.pref_repo.set_preference(pref.key, pref.value)

        backup_mgr = BackupManager(self.db_manager)
        backup_dir = Path(self.temp_dir.name) / "backups"
        backup_file = backup_mgr.backup_database(backup_dir=backup_dir)

        self.assertTrue(backup_file.exists())
        self.assertTrue(backup_mgr.verify_integrity())

        # Modify database state
        self.pref_repo.set_preference("backup_test_key", "modified_val")
        self.assertEqual(self.pref_repo.get_preference("backup_test_key"), "modified_val")

        # Restore from backup
        restored = backup_mgr.restore_database(backup_file)
        self.assertTrue(restored)
        self.assertEqual(self.pref_repo.get_preference("backup_test_key"), "backup_test_val")


if __name__ == "__main__":
    unittest.main()
