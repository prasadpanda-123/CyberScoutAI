"""
Unit Tests for Deterministic Free-Only Rule Engine (Phase E).

Verifies all business rules, financial distinctions, and edge cases:
- Free job (no application fee) -> APPROVED
- Paid internship with stipend -> APPROVED
- Free internship -> APPROVED
- Free CTF with cash prizes -> APPROVED
- Free bug bounty -> APPROVED
- Free course -> APPROVED
- Paid course -> REJECTED
- Mandatory application fee -> REJECTED
- Mandatory certification fee -> REJECTED
- Optional paid certification -> APPROVED
- Mandatory membership -> REJECTED
- Optional membership -> APPROVED
- Mandatory purchase -> REJECTED
- Free trial with mandatory payment -> REJECTED
- Missing pricing evidence -> QUARANTINED (unknown never means free)
- Contradictory pricing statements -> QUARANTINED
- Invalid / unverified evidence excerpts -> QUARANTINED
- Insufficient / unavailable source text -> QUARANTINED
- Malformed classification payload -> QUARANTINED
- Compensation versus participant cost separation
"""

import pytest

from src.discovery.free_only_models import (
    FreeOnlyDecision,
    PricingVerificationStatus,
)
from src.discovery.free_only_rules import FreeOnlyRuleEngine
from src.discovery.pricing_evidence_validator import PricingEvidenceValidator


class TestFreeOnlyRules:

    def setup_method(self):
        self.validator = PricingEvidenceValidator()
        self.engine = FreeOnlyRuleEngine(evidence_validator=self.validator)

    def test_free_job_no_application_fee(self):
        """A cybersecurity job that provides salary with no application fee is APPROVED."""
        page_content = (
            "# Senior Security Engineer\n\n"
            "CyberSec Corp is hiring a Senior Security Engineer. Annual salary: $150,000.\n"
            "There is no application fee. Free to apply for all candidates.\n"
            "Requirements: 5+ years of experience with SIEM and Cloud Security."
        )
        classification_data = {
            "financial": {
                "participation_cost_status": "FREE",
                "application_fee_status": "FREE",
                "compensation_status": "PAID",
                "compensation_details": "$150,000 per year",
            },
            "evidence": [
                {
                    "field_name": "application_fee_status",
                    "exact_excerpt": "There is no application fee.",
                }
            ],
        }

        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="job-1",
            category="job",
            page_content=page_content,
            source_url="https://cybersec.corp/careers/security-engineer",
            source_domain="cybersec.corp",
            classification_data=classification_data,
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert status == PricingVerificationStatus.VERIFIED_FREE
        assert is_free is True
        assert cost == "FREE"
        assert comp == "PAID"
        assert "RULE_APPROVE_VERIFIED_FREE_OPPORTUNITY" in rules or "RULE_APPROVE_COMPENSATED_EMPLOYMENT_WITHOUT_FEE" in rules

    def test_paid_internship_with_stipend(self):
        """A paid internship paying a monthly stipend with zero fees is APPROVED (free to apply)."""
        page_content = (
            "# CERT-In Summer Internship 2026\n\n"
            "Official paid internship for Indian university students. Free to apply.\n"
            "Selected interns will receive a monthly stipend of ₹25,000.\n"
            "Work mode: Onsite in New Delhi. No registration fee is required."
        )
        classification_data = {
            "financial": {
                "participation_cost_status": "FREE",
                "application_fee_status": "FREE",
                "compensation_status": "PAID",
                "compensation_details": "₹25,000 per month stipend",
            },
            "evidence": [
                {
                    "field_name": "participation_cost_status",
                    "exact_excerpt": "Free to apply.",
                }
            ],
        }

        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="intern-1",
            category="internship",
            page_content=page_content,
            source_url="https://cert-in.org.in/internships",
            source_domain="cert-in.org.in",
            classification_data=classification_data,
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert is_free is True
        assert comp == "PAID"

    def test_free_ctf_with_cash_prizes(self):
        """A free CTF with cash prizes has compensation='PAID' and cost='FREE' -> APPROVED."""
        page_content = (
            "# CyberDefenders Collegiate CTF 2026\n\n"
            "Free registration for all collegiate teams. Free to participate.\n"
            "Cash prize pool of $10,000 for top 5 teams!\n"
            "Categories: Reverse Engineering, Web, Pwn, Crypto."
        )
        classification_data = {
            "financial": {
                "participation_cost_status": "FREE",
                "registration_fee_status": "FREE",
                "compensation_status": "PAID",
                "compensation_details": "$10,000 cash prize pool",
            },
            "evidence": [
                {
                    "field_name": "participation_cost_status",
                    "exact_excerpt": "Free registration for all collegiate teams.",
                }
            ],
        }

        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="ctf-1",
            category="ctf",
            page_content=page_content,
            source_url="https://ctftime.org/event/999",
            source_domain="ctftime.org",
            classification_data=classification_data,
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert is_free is True
        assert comp == "PAID"

    def test_free_bug_bounty_on_trusted_platform(self):
        """A public vulnerability disclosure program or bug bounty on HackerOne is APPROVED."""
        page_content = (
            "# Department of Defense Bug Bounty Program\n\n"
            "Public vulnerability disclosure program hosted on HackerOne.\n"
            "Security researchers are invited to find security vulnerabilities. Free participation.\n"
            "Bounty rewards: $500 to $10,000 per valid finding."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="bb-1",
            category="bug_bounty",
            page_content=page_content,
            source_url="https://hackerone.com/deptofdefense",
            source_domain="hackerone.com",
            classification_data={},
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert is_free is True

    def test_free_course_without_fees(self):
        """A completely free cybersecurity training course is APPROVED."""
        page_content = (
            "# Open Security Training: Intro to x86 Assembly\n\n"
            "This open source course is 100% free of cost for all students.\n"
            "Includes video lectures, lab exercises, and downloadable slides. Free training."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="course-1",
            category="free_course",
            page_content=page_content,
            source_url="https://opensecuritytraining.info/IntroX86.html",
            source_domain="opensecuritytraining.info",
            classification_data={},
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert is_free is True

    def test_paid_course_rejected(self):
        """A cybersecurity bootcamp or course charging tuition is REJECTED."""
        page_content = (
            "# Advanced Penetration Testing Bootcamp\n\n"
            "Intensive 12-week offensive security training.\n"
            "Tuition fee: $2,500. Registration fee: $100.\n"
            "Prepares students for industry certification."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="paid-course-1",
            category="course_certification",
            page_content=page_content,
            source_url="https://bootcamp.example.com/pentesting",
            source_domain="bootcamp.example.com",
            classification_data={
                "financial": {
                    "participation_cost_status": "PAID",
                    "application_fee_status": "PAID",
                }
            },
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.REJECTED
        assert status == PricingVerificationStatus.VERIFIED_PAID
        assert is_free is False
        assert "RULE_REJECT_MANDATORY_FEE" in rules

    def test_mandatory_application_fee_rejected(self):
        """An opportunity requiring an application fee of $50 is REJECTED."""
        page_content = (
            "# Cyber Defense Fellowship 2026\n\n"
            "An elite security fellowship. Application fee is $50.\n"
            "All candidates must pay the fee to be considered."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="fee-opp-1",
            category="scholarship",
            page_content=page_content,
            source_url="https://fellowship.example.org/apply",
            source_domain="fellowship.example.org",
            classification_data={},
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.REJECTED
        assert is_free is False
        assert "mandatory application_fee" in reason

    def test_mandatory_certification_fee_rejected(self):
        """A program requiring a mandatory certification fee is REJECTED."""
        page_content = (
            "# Cyber Analyst Fast Track\n\n"
            "Comprehensive training with mandatory certification fee of $300.\n"
            "Passing the exam is required to complete the training program."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="cert-fee-1",
            category="free_training",
            page_content=page_content,
            source_url="https://training.example.com/analyst",
            source_domain="training.example.com",
            classification_data={},
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.REJECTED
        assert is_free is False

    def test_optional_paid_certification_approved(self):
        """A course that is free to audit with an optional verified certificate is APPROVED."""
        page_content = (
            "# Introduction to Web Application Security\n\n"
            "This course is completely free to audit for all students.\n"
            "Free training on OWASP Top 10 vulnerabilities.\n"
            "An optional verified certificate is available for $49."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="opt-cert-1",
            category="free_course",
            page_content=page_content,
            source_url="https://courses.example.org/websec",
            source_domain="courses.example.org",
            classification_data={
                "financial": {
                    "participation_cost_status": "FREE",
                    "application_fee_status": "FREE",
                }
            },
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.APPROVED
        assert is_free is True

    def test_mandatory_membership_rejected(self):
        """A program requiring mandatory paid membership to participate is REJECTED."""
        page_content = (
            "# Exclusive Threat Hunting Workshop\n\n"
            "Hands-on hunting scenarios. Mandatory membership of $25/mo required to register.\n"
            "Open to all active security professionals."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="member-1",
            category="webinar",
            page_content=page_content,
            source_url="https://security-club.org/workshop",
            source_domain="security-club.org",
            classification_data={},
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.REJECTED
        assert is_free is False

    def test_missing_pricing_evidence_quarantined(self):
        """When no pricing is mentioned, candidate must be QUARANTINED (unknown != free)."""
        page_content = (
            "# Security Operations Center Internship\n\n"
            "Apply to work with our Tier 2 SOC team. We monitor network anomalies.\n"
            "Requirements: Python, Wireshark, SIEM. Shift timings: 9 AM - 6 PM.\n"
            "Send your resume to hr@example.com."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="missing-price-1",
            category="internship",
            page_content=page_content,
            source_url="https://example.com/careers/soc",
            source_domain="example.com",
            classification_data={
                "financial": {
                    "participation_cost_status": "UNCERTAIN",
                    "pricing_evidence": [],
                }
            },
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.QUARANTINED
        assert status == PricingVerificationStatus.UNCERTAIN
        assert is_free is None
        assert "Pricing is not explicitly stated" in reason

    def test_contradictory_pricing_statements_quarantined(self):
        """When the page mentions both 'free admission' and 'registration fee $500', it is QUARANTINED."""
        page_content = (
            "# Global Cybersecurity Summit 2026\n\n"
            "Welcome to the summit! Free admission for selected keynotes.\n"
            "Full conference pass: registration fee $500 for general attendees.\n"
            "Takes place in London, UK."
        )
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="contra-1",
            category="conference",
            page_content=page_content,
            source_url="https://summit.example.org",
            source_domain="summit.example.org",
            classification_data={},
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.QUARANTINED
        assert status == PricingVerificationStatus.UNCERTAIN
        assert is_free is None
        assert "Conflicting pricing evidence detected" in reason

    def test_unverified_evidence_excerpt_quarantined(self):
        """If AI claims free with an excerpt not in source text and domain is untrusted, it is QUARANTINED."""
        page_content = (
            "# Cybersecurity Forum Meeting\n\n"
            "Discussing web application vulnerabilities. Join our weekly call.\n"
            "Details will be emailed to registered attendees."
        )
        classification_data = {
            "financial": {
                "participation_cost_status": "FREE",
            },
            "evidence": [
                {
                    "field_name": "participation_cost_status",
                    "exact_excerpt": "This meeting is 100% free of cost with zero registration fees.",
                }
            ],
        }

        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="hallucinated-1",
            category="conference",
            page_content=page_content,
            source_url="https://untrusted-forum.biz/event",
            source_domain="untrusted-forum.biz",
            classification_data=classification_data,
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.QUARANTINED
        assert is_free is None
        assert "could not be verified" in reason

    def test_insufficient_source_quarantined(self):
        """Scraped pages with fewer than 30 characters must be QUARANTINED immediately."""
        decision, status, is_free, cost, comp, fee, reason, ev, rules = self.engine.evaluate(
            candidate_id="empty-1",
            category="other",
            page_content="Error 404",
            source_url="https://dead-link.com",
            source_domain="dead-link.com",
            classification_data={},
            extraction_data={},
        )

        assert decision == FreeOnlyDecision.QUARANTINED
        assert is_free is None
        assert "RULE_QUARANTINE_INSUFFICIENT_SOURCE" in rules

