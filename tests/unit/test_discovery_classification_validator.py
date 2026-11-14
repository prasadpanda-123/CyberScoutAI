"""
Unit Tests for AI Classification Validator (Phase D).

Verifies:
- Schema validation: all 16 supported opportunity categories
- Missing required fields rejection
- Invalid category and enum rejection
- Numeric confidence bounds enforcement [0.0, 1.0]
- Date format validation (ISO / readable format)
- Financial contradiction detection (e.g. FREE participation + PAID application fee)
- Verbatim evidence validation against extracted source text
- Ungrounded claims rejection (excerpts not in source page)
- Zero-hallucination downgrading of unevidenced 'FREE' claims to 'UNCERTAIN'
"""

import pytest

from src.discovery.classification_models import (
    ClassificationCategory,
    FeeStatus,
    ParticipationCostStatus,
)
from src.discovery.classification_validator import ClassificationValidator


class TestClassificationValidator:

    def setup_method(self):
        self.validator = ClassificationValidator()
        self.sample_page_content = (
            "# CERT-In Cybersecurity Research Fellowship 2026\n\n"
            "Official government fellowship program in New Delhi, India.\n"
            "This research fellowship is completely free of cost for all accepted scholars.\n"
            "Stipend provided: Rs 45,000 per month for selected fellows.\n"
            "Work mode: Onsite at CERT-In headquarters in New Delhi.\n"
            "Required skills: Python, Reverse Engineering, Threat Hunting, and Memory Forensics.\n"
            "Eligibility: Master's degree in Computer Science or Information Security.\n"
            "Application deadline: December 31, 2026. Apply online at cert-in.org.in.\n"
        )

    def _get_valid_payload(self) -> dict:
        return {
            "title": "CERT-In Cybersecurity Research Fellowship 2026",
            "description": "Government cybersecurity research fellowship with stipend in New Delhi.",
            "organization": "CERT-In",
            "category": "research_opportunity",
            "subcategory": "threat hunting fellowship",
            "required_skills": ["Python", "Reverse Engineering", "Threat Hunting"],
            "preferred_skills": ["Memory Forensics"],
            "cybersecurity_domain": "Threat Intelligence",
            "experience_level": "intermediate",
            "eligibility": {
                "education": "Master's degree in Computer Science",
                "academic_year": None,
                "experience": None,
                "age_restrictions": None,
                "countries": ["India"],
                "other_requirements": [],
            },
            "location": {
                "country": "India",
                "region": "Delhi",
                "city": "New Delhi",
                "work_mode": "onsite",
                "global_eligibility": False,
            },
            "dates": {
                "published_at": None,
                "application_open": None,
                "application_deadline": "2026-12-31",
                "event_start": None,
                "event_end": None,
                "timezone": "IST",
            },
            "financial": {
                "participation_cost_status": "FREE",
                "application_fee_status": "FREE",
                "registration_fee_status": "FREE",
                "mandatory_purchase_status": "FREE",
                "mandatory_paid_certification_status": "FREE",
                "mandatory_membership_status": "FREE",
                "compensation_status": "PAID",
                "compensation_details": "Rs 45,000 per month stipend",
                "pricing_evidence": ["This research fellowship is completely free of cost for all accepted scholars."],
            },
            "evidence": [
                {
                    "field_name": "application_deadline",
                    "exact_excerpt": "Application deadline: December 31, 2026.",
                    "source_url": "https://cert-in.org.in/fellowship",
                },
                {
                    "field_name": "participation_cost_status",
                    "exact_excerpt": "This research fellowship is completely free of cost for all accepted scholars.",
                    "source_url": "https://cert-in.org.in/fellowship",
                },
                {
                    "field_name": "work_mode",
                    "exact_excerpt": "Work mode: Onsite at CERT-In headquarters in New Delhi.",
                    "source_url": "https://cert-in.org.in/fellowship",
                },
            ],
            "confidence": 0.95,
        }

    def test_valid_payload_passes(self):
        """A complete, well-formed payload corroborated by page evidence passes validation."""
        payload = self._get_valid_payload()
        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-1",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        assert is_valid is True
        assert len(errors) == 0
        assert result is not None
        assert result.category == "research_opportunity"
        assert result.confidence == 0.95
        assert result.financial.participation_cost_status == "FREE"
        assert result.financial.compensation_status == "PAID"

    def test_all_16_categories_accepted(self):
        """Validator must accept all 16 canonical cybersecurity opportunity categories."""
        for cat in ClassificationCategory:
            payload = self._get_valid_payload()
            payload["category"] = cat.value
            is_valid, errors, result = self.validator.validate(
                raw_output=payload,
                candidate_id="cand-cat",
                source_url="https://cert-in.org.in/fellowship",
                source_content=self.sample_page_content,
                provider="groq",
                model="llama-3.3-70b-versatile",
            )
            assert is_valid is True
            assert result.category == cat.value

    def test_missing_required_fields_fails(self):
        """Payload missing required top-level fields must fail validation."""
        payload = self._get_valid_payload()
        del payload["required_skills"]
        del payload["confidence"]

        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-missing",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        assert is_valid is False
        assert any("required_skills" in e for e in errors)
        assert any("confidence" in e for e in errors)
        assert result is None

    def test_invalid_category_fails(self):
        """Unrecognized category strings must be rejected."""
        payload = self._get_valid_payload()
        payload["category"] = "crypto_trading_ico"

        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-bad-cat",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        assert is_valid is False
        assert any("Invalid category 'crypto_trading_ico'" in e for e in errors)

    def test_confidence_out_of_bounds_fails(self):
        """Confidence score outside [0.0, 1.0] must fail validation."""
        payload = self._get_valid_payload()
        payload["confidence"] = 1.45

        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-conf",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        assert is_valid is False
        assert any("outside valid range" in e for e in errors)

    def test_financial_contradiction_fails(self):
        """Claiming free participation while listing a paid application fee must fail validation."""
        payload = self._get_valid_payload()
        payload["financial"]["participation_cost_status"] = "FREE"
        payload["financial"]["application_fee_status"] = "PAID"

        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-contra",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        assert is_valid is False
        assert any("Financial contradiction" in e for e in errors)

    def test_ungrounded_evidence_excerpt_fails(self):
        """An evidence excerpt that does NOT exist in the source content must be rejected."""
        payload = self._get_valid_payload()
        payload["evidence"].append({
            "field_name": "eligibility",
            "exact_excerpt": "Applicants must hold a PhD from MIT and 10 years of NSA experience.",
            "source_url": "https://cert-in.org.in/fellowship",
        })

        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-hallucinated",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        assert is_valid is False
        assert any("Ungrounded claim: evidence excerpt" in e for e in errors)

    def test_unevidenced_free_claim_downgraded_to_uncertain(self):
        """Claiming FREE participation without pricing evidence must be downgraded to UNCERTAIN."""
        payload = self._get_valid_payload()
        # Remove pricing evidence from payload and evidence list
        payload["financial"]["pricing_evidence"] = []
        payload["evidence"] = [
            e for e in payload["evidence"] if e["field_name"] != "participation_cost_status"
        ]

        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-downgrade",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        # Passes validation because the system safely downgraded the unverified free claim
        assert is_valid is True
        assert result.financial.participation_cost_status == ParticipationCostStatus.UNCERTAIN.value

    def test_short_description_fails(self):
        """A description with fewer than 15 characters must fail validation."""
        payload = self._get_valid_payload()
        payload["description"] = "Short job."

        is_valid, errors, result = self.validator.validate(
            raw_output=payload,
            candidate_id="cand-short",
            source_url="https://cert-in.org.in/fellowship",
            source_content=self.sample_page_content,
            provider="groq",
            model="llama-3.3-70b-versatile",
        )

        assert is_valid is False
        assert any("Description is too short" in e for e in errors)

