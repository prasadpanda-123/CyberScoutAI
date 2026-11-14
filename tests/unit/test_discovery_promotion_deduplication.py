"""
Unit Tests for Phase F Production Deduplication Engine.
"""

import pytest

from src.discovery.production_deduplication import ProductionDeduplicator
from src.models.opportunity import Opportunity


class TestProductionDeduplication:
    """Test suite for layered production deduplication rules."""

    def setup_method(self):
        self.deduplicator = ProductionDeduplicator()

    def test_canonical_url_normalization(self):
        """Verifies URL canonicalization strips tracking params and standardizes scheme/host."""
        url_a = "https://WWW.EXAMPLE.COM/careers/cyber-analyst/?utm_source=linkedin&utm_campaign=summer#apply"
        url_b = "https://example.com/careers/cyber-analyst"

        canon_a = self.deduplicator.canonicalize_url(url_a)
        canon_b = self.deduplicator.canonicalize_url(url_b)

        assert canon_a == canon_b
        assert "utm_source" not in canon_a
        assert "#apply" not in canon_a

    def test_exact_url_hash_match(self):
        """Verifies duplicate candidate matches existing opportunity by url_hash."""
        existing_opp = Opportunity(
            id="opp-101",
            title="Senior SOC Analyst",
            url="https://cybercorp.com/jobs/soc-analyst",
            source_id="tavily",
            company="CyberCorp",
        )

        candidate_data = {
            "title": "Senior SOC Analyst",
            "canonical_url": "https://cybercorp.com/jobs/soc-analyst?utm_source=twitter",
            "organization": "CyberCorp",
        }

        match = self.deduplicator.find_match(candidate_data, [existing_opp])
        assert match is not None
        matched_opp, reason = match
        assert matched_opp.id == "opp-101"
        assert reason in ("EXACT_URL_HASH_MATCH", "CANONICAL_URL_MATCH")

    def test_identity_fingerprint_match(self):
        """Verifies identity fingerprint matches even if URLs have minor path differences."""
        existing_opp = Opportunity(
            id="opp-102",
            title="CERT-In Summer Cyber Security Internship 2026",
            url="https://cert-in.org.in/internships/2026/view",
            source_id="tavily",
            company="CERT-In",
            category="internship",
            description="Selected interns will receive hands-on incident response experience.",
        )

        candidate_data = {
            "title": "CERT-In Summer Cyber Security Internship 2026",
            "canonical_url": "https://cert-in.org.in/careers/summer-internship-apply",
            "organization": "CERT-In",
            "category": "internship",
            "description": "Selected interns will receive hands-on incident response experience.",
        }

        match = self.deduplicator.find_match(candidate_data, [existing_opp])
        assert match is not None
        matched_opp, reason = match
        assert matched_opp.id == "opp-102"
        assert reason in ("IDENTITY_FINGERPRINT_MATCH", "ORG_AND_TITLE_MATCH")

    def test_different_opportunities_from_same_org_not_deduplicated(self):
        """
        Crucial: Different opportunities from the same organization (e.g. Google GSoC vs Google Internship)
        must NEVER be merged into a duplicate.
        """
        existing_opp = Opportunity(
            id="opp-google-gsoc",
            title="Google Summer of Code Security Mentorship",
            url="https://summerofcode.withgoogle.com",
            source_id="tavily",
            company="Google",
            category="fellowship",
            description="Open source cybersecurity development mentorship for students.",
        )

        candidate_data = {
            "title": "Google Cloud Security Engineering Internship 2026",
            "canonical_url": "https://careers.google.com/jobs/results/security-intern-2026",
            "organization": "Google",
            "category": "internship",
            "description": "Paid 12-week summer internship working on cloud infrastructure protection.",
        }

        match = self.deduplicator.find_match(candidate_data, [existing_opp])
        assert match is None, "Distinct roles from the same organization must not be merged"

    def test_detect_meaningful_changes(self):
        """Verifies change detector identifies updated deadlines and richer descriptions."""
        existing_opp = Opportunity(
            id="opp-103",
            title="Nullcon Goa CTF 2026",
            url="https://nullcon.net/goa-2026/ctf",
            source_id="tavily",
            company="Nullcon",
            deadline="2026-04-01",
            description="Brief CTF overview.",
        )

        candidate_updated = {
            "title": "Nullcon Goa CTF 2026",
            "canonical_url": "https://nullcon.net/goa-2026/ctf",
            "organization": "Nullcon",
            "deadline": "2026-04-15", # Extended deadline
            "description": "Detailed multi-stage capture the flag competition featuring binary exploitation, cryptography, reverse engineering, web security, and cloud security challenges with cash awards.",
        }

        changes = self.deduplicator.detect_meaningful_changes(candidate_updated, existing_opp)
        assert "deadline" in changes
        assert "description" in changes

