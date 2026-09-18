"""
Phase 2 Unit Tests: Collector Contract & NormalizedOpportunityDTO.

Tests:
- 5-phase contract: discover(), fetch(), parse(), validate(), normalize()
- NormalizedOpportunityDTO fields completeness and defaults
- Granular free/paid, stipend, and certificate models:
    - FREE course + PAID certificate
    - FREE internship + PAID stipend
    - FREE CTF
    - PAID course
    - FREE audit + paid certification
- Honest unknown handling (no fabricated values)
- DTO to Opportunity conversion & pipeline compatibility
- Provenance preservation (source_id, url, canonical_url, raw_payload)
"""

import unittest
from datetime import datetime, timezone

from src.collectors.base import BaseCollector
from src.models.enums import (
    CertificateAvailable,
    CertificateCost,
    OpportunityType,
    PricingType,
    StipendType,
)
from src.models.opportunity import Opportunity
from src.models.opportunity_dto import NormalizedOpportunityDTO
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository


class MockContractCollector(BaseCollector):
    """Concrete mock collector implementing the 5-phase interface for contract testing."""

    @property
    def collector_name(self) -> str:
        return "mock_contract_collector"

    def discover(self, task):
        return ["https://example.com/api/v1/item1", "https://example.com/api/v1/item2"]

    def fetch(self, endpoint):
        return {
            "title": f"Test Course for {endpoint}",
            "desc": "A comprehensive cybersecurity course.",
            "url": endpoint,
            "cost": 0.0,
            "cert_cost": 49.0,
            "stipend": 0.0,
        }

    def parse(self, raw_content):
        return [raw_content]

    def validate(self, candidate):
        return bool(candidate.get("title") and candidate.get("url"))

    def normalize(self, validated_candidate):
        return NormalizedOpportunityDTO(
            title=validated_candidate["title"],
            description=validated_candidate["desc"],
            url=validated_candidate["url"],
            canonical_url=validated_candidate["url"],
            source_id="test_mock_source",
            provider="Test Provider",
            opportunity_type=OpportunityType.COURSE,
            pricing_type=PricingType.FREE,
            price_amount=0.0,
            currency="USD",
            is_free=True,
            certificate_available=CertificateAvailable.YES,
            certificate_cost=CertificateCost.PAID,
            certificate_fee=49.0,
            raw_payload=validated_candidate,
        )


class TestPhase2CollectorContract(unittest.TestCase):
    """Validates the 5-phase collector interface and DTO representations."""

    def test_collector_5_phase_contract_execution(self):
        """Verify that discover -> fetch -> parse -> validate -> normalize pipeline completes cleanly."""
        collector = MockContractCollector("test_mock_source")
        task = {"source_id": "test_mock_source"}

        # 1. Discover
        endpoints = collector.discover(task)
        self.assertEqual(len(endpoints), 2)

        # 2. Fetch
        fetched = collector.fetch(endpoints[0])
        self.assertIn("title", fetched)

        # 3. Parse
        parsed_candidates = collector.parse(fetched)
        self.assertEqual(len(parsed_candidates), 1)

        # 4. Validate
        is_valid = collector.validate(parsed_candidates[0])
        self.assertTrue(is_valid)

        # 5. Normalize
        dto = collector.normalize(parsed_candidates[0])
        self.assertIsInstance(dto, NormalizedOpportunityDTO)
        self.assertEqual(dto.title, "Test Course for https://example.com/api/v1/item1")
        self.assertEqual(dto.pricing_type, PricingType.FREE)
        self.assertEqual(dto.certificate_cost, CertificateCost.PAID)

        # Verify collect(task) facade backward compatibility
        result = collector.collect(task)
        self.assertGreaterEqual(len(result.items), 2)
        self.assertIn("title", result.items[0])
        opp_converted = dto.to_opportunity()
        self.assertIsInstance(opp_converted, Opportunity)

    def test_free_course_plus_paid_certificate_representation(self):
        """Scenario: FREE audit course with a PAID certificate ($49)."""
        dto = NormalizedOpportunityDTO(
            title="Introduction to Network Defense",
            description="Audit this course for free, pay for certificate.",
            url="https://coursera.org/learn/intro-netsec",
            source_id="coursera",
            opportunity_type=OpportunityType.COURSE,
            pricing_type=PricingType.FREE,
            is_free=True,
            price_amount=0.0,
            currency="USD",
            free_conditions="Free to audit course material; certificate requires payment",
            certificate_available=CertificateAvailable.YES,
            certificate_cost=CertificateCost.PAID,
            certificate_fee=49.0,
        )

        self.assertTrue(dto.is_free)
        self.assertEqual(dto.pricing_type, PricingType.FREE)
        self.assertEqual(dto.certificate_available, CertificateAvailable.YES)
        self.assertEqual(dto.certificate_cost, CertificateCost.PAID)
        self.assertEqual(dto.certificate_fee, 49.0)

        # Convert to Opportunity model
        opp = dto.to_opportunity()
        self.assertFalse(opp.paid)  # course material is not paid
        self.assertTrue(opp.certificate)
        self.assertEqual(opp.pricing_type, PricingType.FREE.value)
        self.assertEqual(opp.certificate_cost, CertificateCost.PAID.value)
        self.assertEqual(opp.certificate_fee, 49.0)

    def test_free_internship_with_paid_stipend_representation(self):
        """Scenario: FREE application internship with a PAID stipend (15,000 INR/month)."""
        dto = NormalizedOpportunityDTO(
            title="Cyber Security Analyst Intern",
            description="6-month government cyber defense internship with stipend.",
            url="https://internship.aicte-india.org/opp1",
            source_id="aicte_internships",
            opportunity_type=OpportunityType.INTERNSHIP,
            pricing_type=PricingType.FREE,
            is_free=True,
            application_fee=0.0,
            stipend_type=StipendType.PAID,
            stipend_amount=15000.0,
            stipend_currency="INR",
        )

        self.assertTrue(dto.is_free)
        self.assertEqual(dto.stipend_type, StipendType.PAID)
        self.assertEqual(dto.stipend_amount, 15000.0)
        self.assertEqual(dto.stipend_currency, "INR")

        opp = dto.to_opportunity()
        self.assertEqual(opp.stipend_type, StipendType.PAID.value)
        self.assertEqual(opp.stipend_amount, 15000.0)
        self.assertEqual(opp.stipend_currency, "INR")

    def test_free_ctf_representation(self):
        """Scenario: FREE CTF competition with NO fees and NO stipend."""
        dto = NormalizedOpportunityDTO(
            title="picoCTF 2026",
            description="Free beginner-friendly security challenge.",
            url="https://picoctf.org/competition",
            source_id="picoctf",
            opportunity_type=OpportunityType.CTF,
            pricing_type=PricingType.FREE,
            is_free=True,
            price_amount=0.0,
            application_fee=0.0,
            stipend_type=StipendType.NONE,
            certificate_available=CertificateAvailable.YES,
            certificate_cost=CertificateCost.FREE,
        )

        opp = dto.to_opportunity()
        self.assertTrue(opp.is_free)
        self.assertFalse(opp.paid)
        self.assertEqual(opp.opportunity_type, OpportunityType.CTF.value)
        self.assertEqual(opp.stipend_type, StipendType.NONE.value)
        self.assertEqual(opp.certificate_cost, CertificateCost.FREE.value)

    def test_paid_course_representation(self):
        """Scenario: Pure PAID commercial training course ($199)."""
        dto = NormalizedOpportunityDTO(
            title="Certified Incident Responder Bootcamp",
            description="Commercial comprehensive training program.",
            url="https://training.sans.org/cirb",
            source_id="sans",
            opportunity_type=OpportunityType.COURSE,
            pricing_type=PricingType.PAID,
            is_free=False,
            price_amount=199.0,
            currency="USD",
            certificate_available=CertificateAvailable.YES,
            certificate_cost=CertificateCost.FREE,  # included in course fee
        )

        opp = dto.to_opportunity()
        self.assertFalse(opp.is_free)
        self.assertTrue(opp.paid)
        self.assertEqual(opp.pricing_type, PricingType.PAID.value)
        self.assertEqual(opp.price_amount, 199.0)
        self.assertEqual(opp.price_normalized, "199.0")

    def test_honest_unknown_handling_no_fabricated_data(self):
        """Verify that unknown fields remain UNKNOWN or None rather than being fabricated."""
        dto = NormalizedOpportunityDTO(
            title="Mystery Developer Fellowship",
            url="https://example.org/fellowship",
            source_id="devpost",
        )

        self.assertEqual(dto.pricing_type, PricingType.UNKNOWN)
        self.assertIsNone(dto.price_amount)
        self.assertIsNone(dto.is_free)
        self.assertEqual(dto.stipend_type, StipendType.UNKNOWN)
        self.assertIsNone(dto.stipend_amount)
        self.assertEqual(dto.certificate_available, CertificateAvailable.UNKNOWN)
        self.assertEqual(dto.certificate_cost, CertificateCost.UNKNOWN)

        opp = dto.to_opportunity()
        self.assertIsNone(opp.paid)
        self.assertIsNone(opp.is_free)
        self.assertEqual(opp.pricing_type, PricingType.UNKNOWN.value)
        self.assertEqual(opp.stipend_type, StipendType.UNKNOWN.value)

    def test_provenance_preservation(self):
        """Verify traceability: source_id, url, canonical_url, raw_payload, discovered_at."""
        raw = {"event_id": 9988, "title": "Hack the Future", "sponsor": "CyberCorp"}
        dto = NormalizedOpportunityDTO(
            title="Hack the Future 2026",
            url="https://devpost.com/hackathons/future-2026",
            canonical_url="https://devpost.com/hackathons/future-2026",
            source_id="devpost",
            raw_payload=raw,
        )

        opp = dto.to_opportunity()
        self.assertEqual(opp.source_id, "devpost")
        self.assertEqual(opp.url, "https://devpost.com/hackathons/future-2026")
        self.assertEqual(opp.raw_data.get("event_id"), 9988)
        self.assertTrue(opp.discovered_date)

    def test_opportunity_repository_saves_phase2_pricing(self):
        """Verify that OpportunityRepository persists and queries Phase 2 pricing fields."""
        db = DatabaseManager()
        db.initialize_database()
        repo = OpportunityRepository(db)

        opp = Opportunity(
            title="Phase 2 Cloud Security Internship",
            url="https://example.com/opps/cloud-sec-intern-2026",
            source_id="aicte_internships",
            category="internship",
            opportunity_type=OpportunityType.INTERNSHIP,
            pricing_type=PricingType.FREE,
            is_free=True,
            application_fee=0.0,
            stipend_type=StipendType.PAID,
            stipend_amount=25000.0,
            stipend_currency="INR",
            certificate_available=CertificateAvailable.YES,
            certificate_cost=CertificateCost.FREE,
            score=88,
        )

        opp_id = repo.upsert(opp)
        self.assertIsNotNone(opp_id)

        fetched = repo.get_by_id(opp_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Phase 2 Cloud Security Internship")
        self.assertEqual(fetched.pricing_type, PricingType.FREE.value)
        self.assertEqual(fetched.stipend_type, StipendType.PAID.value)
        self.assertEqual(fetched.stipend_amount, 25000.0)
        self.assertEqual(fetched.stipend_currency, "INR")

        db.close()


if __name__ == "__main__":
    unittest.main()
