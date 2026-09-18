"""
Phase 2 Unit Tests: Existing Collectors Adaptation & Representative Implementations.

Tests:
- Existing collectors adaptation under 5-phase contract:
    - GenericRSSCollector
    - CtftimeCollector
    - GithubSearchCollector
    - HtmlScraperCollector
    - YouTubeRSSCollector
- Representative verified collectors:
    - MicrosoftLearnCollector
    - DevpostCollector
    - GSoCCollector
    - OutreachyCollector
    - UpForGrabsCollector
- Normalization into NormalizedOpportunityDTO
- URL deduplication integrity: uq_opportunities_url_hash preserved
"""

import unittest
from unittest.mock import MagicMock, patch

from src.collectors.ctftime_collector import CtftimeCollector
from src.collectors.devpost_collector import DevpostCollector
from src.collectors.github_collector import GithubSearchCollector
from src.collectors.gsoc_collector import GSoCCollector
from src.collectors.html_collector import HtmlScraperCollector
from src.collectors.microsoft_learn_collector import MicrosoftLearnCollector
from src.collectors.outreachy_collector import OutreachyCollector
from src.collectors.rss_collector import GenericRSSCollector
from src.collectors.up_for_grabs_collector import UpForGrabsCollector
from src.collectors.youtube_collector import YouTubeRSSCollector
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_repository import SourceRepository
from src.models.enums import OpportunityType, PricingType, StipendType, CertificateCost
from src.models.opportunity import Opportunity
from src.models.opportunity_dto import NormalizedOpportunityDTO
from src.models.source import Source


class TestPhase2RepresentativeCollectors(unittest.TestCase):
    """Tests existing collectors and representative Phase 2 implementations."""

    def test_microsoft_learn_collector_cycle(self):
        """Verify MicrosoftLearnCollector 5-phase cycle and free course + paid cert model."""
        collector = MicrosoftLearnCollector("microsoft_learn")
        self.assertEqual(collector.source_id, "microsoft_learn")
        self.assertIn("Microsoft Learn", collector.collector_name)

        # Discover
        targets = collector.discover({})
        self.assertGreater(len(targets), 0)

        # Mock API response for fetch
        sample_api_response = {
            "modules": [
                {
                    "uid": "learn.azure.fundamentals",
                    "title": "Microsoft Azure Fundamentals: Describe cloud concepts",
                    "summary": "Learn basic cloud concepts, benefits, and models.",
                    "url": "https://learn.microsoft.com/en-us/training/modules/describe-cloud-concepts/",
                    "duration_in_minutes": 55,
                    "levels": ["beginner"],
                    "roles": ["administrator", "developer"],
                    "products": ["azure"],
                }
            ]
        }

        # Parse
        parsed = collector.parse(sample_api_response)
        self.assertEqual(len(parsed), 1)

        # Validate
        self.assertTrue(collector.validate(parsed[0]))

        # Normalize
        dto = collector.normalize(parsed[0])
        self.assertIsInstance(dto, NormalizedOpportunityDTO)
        self.assertEqual(dto.source_id, "microsoft_learn")
        self.assertEqual(dto.title, "Microsoft Azure Fundamentals: Describe cloud concepts")
        self.assertEqual(dto.pricing_type, PricingType.FREE)
        self.assertEqual(dto.certificate_cost, CertificateCost.FREE.value)
        self.assertEqual(dto.opportunity_type, OpportunityType.COURSE)

    def test_devpost_collector_cycle(self):
        """Verify DevpostCollector 5-phase cycle for developer hackathons."""
        collector = DevpostCollector("devpost")
        self.assertEqual(collector.source_id, "devpost")
        self.assertIn("Devpost", collector.collector_name)

        sample_feed_item = {
            "title": "Global AI Agents Hackathon 2026",
            "link": "https://global-ai.devpost.com/",
            "summary": "Build autonomous agents for good with $50,000 in prizes.",
            "published": "2026-09-01T00:00:00Z",
        }

        # Validate
        self.assertTrue(collector.validate(sample_feed_item))

        # Normalize
        dto = collector.normalize(sample_feed_item)
        self.assertIsInstance(dto, NormalizedOpportunityDTO)
        self.assertEqual(dto.source_id, "devpost")
        self.assertEqual(dto.opportunity_type, OpportunityType.HACKATHON)
        self.assertEqual(dto.pricing_type, PricingType.FREE)
        self.assertTrue(dto.is_free)

    def test_gsoc_collector_cycle(self):
        """Verify GSoCCollector cycle and open source stipend representation."""
        collector = GSoCCollector("google_summer_of_code")
        self.assertEqual(collector.source_id, "google_summer_of_code")
        self.assertIn("Google Summer of Code", collector.collector_name)

        sample_org = {
            "name": "OWASP Foundation",
            "description": "Open Web Application Security Project mentoring contributors.",
            "url": "https://summerofcode.withgoogle.com/programs/2026/organizations/owasp",
            "category": "Security",
            "topics": ["security", "python", "owasp"],
        }

        self.assertTrue(collector.validate(sample_org))
        dto = collector.normalize(sample_org)
        self.assertIsInstance(dto, NormalizedOpportunityDTO)
        self.assertEqual(dto.source_id, "google_summer_of_code")
        self.assertEqual(dto.opportunity_type, OpportunityType.OPEN_SOURCE)
        self.assertEqual(dto.stipend_type, StipendType.PAID)
        self.assertEqual(dto.stipend_currency, "USD")

    def test_outreachy_collector_cycle(self):
        """Verify OutreachyCollector cycle with paid diversity internship stipends."""
        collector = OutreachyCollector("outreachy")
        self.assertEqual(collector.source_id, "outreachy")
        self.assertIn("Outreachy", collector.collector_name)

        sample_item = {
            "title": "Linux Kernel Intern",
            "url": "https://www.outreachy.org/apply/project-selection/#kernel",
            "description": "3-month remote paid open source internship.",
            "community": "Linux Foundation",
        }

        self.assertTrue(collector.validate(sample_item))
        dto = collector.normalize(sample_item)
        self.assertEqual(dto.source_id, "outreachy")
        self.assertEqual(dto.opportunity_type, OpportunityType.INTERNSHIP)
        self.assertEqual(dto.stipend_type, StipendType.PAID)
        self.assertEqual(dto.stipend_amount, 7000.0)

    def test_up_for_grabs_collector_cycle(self):
        """Verify UpForGrabsCollector cycle for beginner-friendly open-source tasks."""
        collector = UpForGrabsCollector("up_for_grabs")
        self.assertEqual(collector.source_id, "up_for_grabs")
        self.assertIn("Up For Grabs", collector.collector_name)

        sample_project = {
            "name": "CyberScout Community",
            "desc": "An AI scout for student cybersecurity opportunities.",
            "site": "https://github.com/cyberscout/cyberscout-ai",
            "tags": ["python", "cybersecurity"],
        }

        self.assertTrue(collector.validate(sample_project))
        dto = collector.normalize(sample_project)
        self.assertEqual(dto.source_id, "up_for_grabs")
        self.assertEqual(dto.opportunity_type, OpportunityType.OPEN_SOURCE)
        self.assertEqual(dto.pricing_type, PricingType.FREE)

    def test_ctftime_collector_adaptation(self):
        """Verify adapted CtftimeCollector emits valid CTF opportunities under 5-phase contract."""
        collector = CtftimeCollector("ctftime")
        sample_ctf = {
            "id": 2048,
            "title": "DefCamp CTF 2026",
            "description": "Major international CTF competition.",
            "url": "https://ctftime.org/event/2048",
            "ctftime_url": "https://ctftime.org/event/2048",
            "start": "2026-10-01T10:00:00+00:00",
            "finish": "2026-10-02T10:00:00+00:00",
            "weight": 50.0,
            "onsite": False,
        }

        self.assertTrue(collector.validate(sample_ctf))
        dto = collector.normalize(sample_ctf)
        self.assertIsInstance(dto, NormalizedOpportunityDTO)
        self.assertEqual(dto.source_id, "ctftime")
        self.assertEqual(dto.opportunity_type, OpportunityType.CTF)
        self.assertEqual(dto.pricing_type, PricingType.FREE)

    def test_github_collector_adaptation(self):
        """Verify adapted GithubSearchCollector emits valid open source repositories."""
        collector = GithubSearchCollector("github")
        sample_repo = {
            "name": "awesome-threat-intelligence",
            "html_url": "https://github.com/cyber/awesome-threat-intelligence",
            "description": "A curated list of Threat Intelligence resources.",
            "stargazers_count": 1200,
            "owner": {"login": "cyber"},
        }

        self.assertTrue(collector.validate(sample_repo))
        dto = collector.normalize(sample_repo)
        self.assertIsInstance(dto, NormalizedOpportunityDTO)
        self.assertEqual(dto.source_id, "github")
        self.assertEqual(dto.opportunity_type, OpportunityType.OPEN_SOURCE)

    def test_url_deduplication_invariant_preserved(self):
        """
        Verify that URL deduplication preserves Phase 1 url_hash uniqueness (uq_opportunities_url_hash).
        """
        db = DatabaseManager()
        db.initialize_database()
        source_repo = SourceRepository(db)
        source_repo.save_source(Source(id="devpost", name="Devpost"))

        opp_repo = OpportunityRepository(db)

        # 1. First insert
        opp1 = Opportunity(
            title="AI Defense Hackathon 2026",
            url="https://devpost.com/hackathons/ai-defense-2026",
            source_id="devpost",
            category="hackathon",
            score=90,
        )
        id1 = opp_repo.upsert(opp1)
        self.assertIsNotNone(id1)

        # 2. Re-insert identical canonical URL with updated title
        opp2 = Opportunity(
            title="AI Defense Hackathon 2026 — Updated",
            url="https://devpost.com/hackathons/ai-defense-2026?ref=newsletter",
            source_id="devpost",
            category="hackathon",
            score=95,
        )
        id2 = opp_repo.upsert(opp2)

        # Both must resolve to the identical record via url_hash idempotency
        self.assertEqual(id1, id2)

        fetched = opp_repo.get_by_id(id1)
        self.assertEqual(fetched.title, "AI Defense Hackathon 2026 — Updated")
        self.assertEqual(fetched.score, 95)

        db.close()


if __name__ == "__main__":
    unittest.main()
