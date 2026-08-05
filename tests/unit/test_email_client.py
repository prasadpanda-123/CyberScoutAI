"""
Unit tests for Notifier Email Client Facade (Phase 7).
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_repository import SourceRepository
from src.models.opportunity import Opportunity
from src.notifier.email_client import EmailClient
from src.notifier.email_sender import EmailSender


class TestEmailClient(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_path=Path(":memory:"))
        self.db_manager.initialize_database()

        # Seed Source
        source_repo = SourceRepository(self.db_manager)
        source_repo.sync_from_config(
            {
                "sources": [
                    {
                        "id": "sans",
                        "name": "SANS Institute",
                        "collection_method": "rss",
                        "default_category": "scholarship",
                    }
                ]
            }
        )

        # Seed Opportunity
        opp_repo = OpportunityRepository(self.db_manager)
        opp = Opportunity(
            title="SANS CyberFastTrack 2026",
            url="https://example.com/sans",
            source_id="sans",
            category="scholarship",
            score=95,
        )
        opp_repo.upsert(opp)

    def tearDown(self):
        self.db_manager.close()

    def test_send_daily_digest(self):
        sender_mock = MagicMock(spec=EmailSender)
        sender_mock.send_email.return_value = "<mock-msg-id@cyberscout.ai>"

        client = EmailClient(db_manager=self.db_manager, email_sender=sender_mock)
        res = client.send_daily_digest()

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["message_id"], "<mock-msg-id@cyberscout.ai>")
        self.assertEqual(res["opportunities_sent"], 1)


if __name__ == "__main__":
    unittest.main()
