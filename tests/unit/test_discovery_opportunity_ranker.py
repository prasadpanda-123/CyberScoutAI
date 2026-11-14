"""
Unit Tests for Phase F Deterministic Opportunity Ranking Engine.
"""

from datetime import datetime, timedelta, timezone
import pytest

from src.discovery.opportunity_ranker import OpportunityRanker


class TestOpportunityRanker:
    """Test suite for deterministic opportunity ranking and priority scoring."""

    def setup_method(self):
        self.ranker = OpportunityRanker()

    def test_deterministic_score_calculation(self):
        """Verifies ranking calculations are 100% deterministic with repeatable results."""
        opp_data = {
            "title": "National Cyber Security Internship 2026",
            "description": "Selected interns will work on threat intelligence, SOC monitoring, and malware analysis.",
            "category": "internship",
            "country_or_scope": "India",
            "remote": False,
            "deadline": (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d"),
            "source_domain": "cert-in.org.in",
            "application_url": "https://cert-in.org.in/apply",
            "required_skills": ["Python", "Network Security", "Threat Hunting"],
            "free_only_decision": "APPROVED",
        }

        score_1, breakdown_1 = self.ranker.calculate_score(opp_data, source_domain="cert-in.org.in")
        score_2, breakdown_2 = self.ranker.calculate_score(opp_data, source_domain="cert-in.org.in")

        assert score_1 == score_2
        assert breakdown_1 == breakdown_2
        assert score_1 >= 75 # High priority opportunity
        assert breakdown_1["regional_relevance_india"] == 15
        assert breakdown_1["official_source_trust"] == 15
        assert breakdown_1["deadline_urgent"] == 15

    def test_india_relevance_prioritization(self):
        """Verifies opportunities located in or focused on India receive designated priority."""
        opp_india = {
            "title": "Cyber Security Trainee",
            "description": "Information security trainee role.",
            "category": "job",
            "country_or_scope": "India",
        }
        opp_other = {
            "title": "Cyber Security Trainee",
            "description": "Information security trainee role.",
            "category": "job",
            "country_or_scope": "Germany",
        }

        score_india, bd_india = self.ranker.calculate_score(opp_india)
        score_other, bd_other = self.ranker.calculate_score(opp_other)

        assert bd_india["regional_relevance_india"] == 15
        assert bd_other["international_scope"] == 6
        assert score_india > score_other

    def test_global_remote_bonus(self):
        """Verifies global remote opportunities receive accessibility bonus."""
        opp_remote = {
            "title": "Bug Bounty Vulnerability Researcher",
            "description": "Remote bug bounty program for ethical hackers.",
            "category": "bug_bounty",
            "country_or_scope": "Global",
            "remote": True,
            "source_domain": "hackerone.com",
        }

        score, breakdown = self.ranker.calculate_score(opp_remote, source_domain="hackerone.com")
        assert breakdown["global_remote_accessibility"] == 12
        assert breakdown["remote_availability"] == 10
        assert breakdown["official_source_trust"] == 15

    def test_deadline_expired_penalty(self):
        """Verifies opportunities with past deadlines receive severe penalty."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
        opp_expired = {
            "title": "Hackathon 2026",
            "description": "Security hackathon.",
            "category": "hackathon",
            "deadline": past_date,
        }

        score, breakdown = self.ranker.calculate_score(opp_expired)
        assert breakdown["deadline_expired_penalty"] == -40

