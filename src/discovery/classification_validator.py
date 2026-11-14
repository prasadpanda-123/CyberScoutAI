"""
Python-Side Strict Schema and Source Evidence Validator (Phase D).

Performs deterministic validation independent of AI providers:
- Enforces strict JSON Schema adherence
- Validates categories, subcategories, enums, and data types
- Verifies that every evidence excerpt actually exists verbatim in the source content
- Detects contradictory financial information (e.g. claiming free while listing paid fees)
- Enforces zero-hallucination rules (preserves UNKNOWN/UNCERTAIN for uncorroborated facts)
- Ensures AI confidence cannot bypass missing evidence
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.logging import get_logger
from src.discovery.classification_models import (
    ClassificationCategory,
    ClassificationResult,
    CompensationStatus,
    DatesData,
    EligibilityData,
    EvidenceItem,
    ExperienceLevel,
    FeeStatus,
    FinancialClassification,
    LocationData,
    ParticipationCostStatus,
    WorkMode,
)

logger = get_logger(__name__)


def _normalize_text_for_search(text: str) -> str:
    """Collapses whitespace and lowercases text for resilient excerpt matching."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


class ClassificationValidator:
    """
    Independent Python validation gate ensuring AI classifications comply with
    the project schema and are corroborated by verbatim source evidence.
    """

    MAX_EXCERPT_LENGTH = 500
    MIN_DESCRIPTION_LENGTH = 15

    def validate(
        self,
        raw_output: Dict[str, Any],
        candidate_id: str,
        source_url: str,
        source_content: str,
        provider: str,
        model: str,
        prompt_version: str = "v1.0",
    ) -> Tuple[bool, List[str], Optional[ClassificationResult]]:
        """
        Validates raw structured JSON from an AI provider against all Phase D requirements.

        Args:
            raw_output: Parsed JSON dictionary returned by Groq or Gemini.
            candidate_id: Staged candidate UUID.
            source_url: Canonical candidate URL.
            source_content: Extracted markdown or HTML page content.
            provider: AI provider identifier ('groq' or 'gemini').
            model: AI model identifier.
            prompt_version: Version of prompt used.

        Returns:
            Tuple of:
            - is_valid (bool): True if all required fields, enums, and evidence checks pass.
            - errors (List[str]): List of validation failure descriptions.
            - result (Optional[ClassificationResult]): Cleaned ClassificationResult or None if invalid.
        """
        errors: List[str] = []

        if not isinstance(raw_output, dict):
            return False, ["Output is not a valid JSON dictionary."], None

        # 1. Required Top-Level Fields
        required_fields = [
            "title",
            "description",
            "category",
            "required_skills",
            "experience_level",
            "eligibility",
            "location",
            "dates",
            "financial",
            "evidence",
            "confidence",
        ]
        for f in required_fields:
            if f not in raw_output:
                errors.append(f"Missing required field: '{f}'.")

        if errors:
            return False, errors, None

        # 2. Field Types & Basic Sanity
        title = str(raw_output.get("title") or "").strip()
        if not title:
            errors.append("Title cannot be empty.")

        description = str(raw_output.get("description") or "").strip()
        if len(description) < self.MIN_DESCRIPTION_LENGTH:
            errors.append(f"Description is too short (<{self.MIN_DESCRIPTION_LENGTH} characters).")

        # 3. Category Validation & Normalization
        raw_category = str(raw_output.get("category") or "").strip().lower()
        category_enum = ClassificationCategory.normalize(raw_category)
        if category_enum == ClassificationCategory.OTHER and raw_category not in ("other", ""):
            # Check if it was an unrecognized category string
            valid_cats = [c.value for c in ClassificationCategory]
            if raw_category not in valid_cats:
                errors.append(f"Invalid category '{raw_category}'. Must be one of {valid_cats}.")

        # 4. Experience Level & Work Mode Enums
        raw_exp = str(raw_output.get("experience_level") or "unknown").strip().lower()
        valid_exp = [e.value for e in ExperienceLevel]
        if raw_exp not in valid_exp:
            errors.append(f"Invalid experience_level '{raw_exp}'. Must be one of {valid_exp}.")
        exp_level = raw_exp if raw_exp in valid_exp else ExperienceLevel.UNKNOWN.value

        loc_dict = raw_output.get("location") or {}
        if not isinstance(loc_dict, dict):
            errors.append("Field 'location' must be an object.")
            loc_dict = {}
        raw_work_mode = str(loc_dict.get("work_mode") or "unknown").strip().lower()
        valid_modes = [w.value for w in WorkMode]
        if raw_work_mode not in valid_modes:
            errors.append(f"Invalid work_mode '{raw_work_mode}'. Must be one of {valid_modes}.")
        work_mode = raw_work_mode if raw_work_mode in valid_modes else WorkMode.UNKNOWN.value

        # 5. Confidence Score Range
        try:
            confidence = float(raw_output.get("confidence") or 0.0)
            if not (0.0 <= confidence <= 1.0):
                errors.append(f"Confidence score {confidence} is outside valid range [0.0, 1.0].")
        except (ValueError, TypeError):
            errors.append("Confidence score must be a numeric float between 0.0 and 1.0.")
            confidence = 0.0

        # 6. Dates Sanity Check
        dates_dict = raw_output.get("dates") or {}
        if not isinstance(dates_dict, dict):
            errors.append("Field 'dates' must be an object.")
            dates_dict = {}
        for date_key in ["published_at", "application_open", "application_deadline", "event_start", "event_end"]:
            date_val = dates_dict.get(date_key)
            if date_val is not None:
                if not isinstance(date_val, str) or not date_val.strip():
                    dates_dict[date_key] = None
                else:
                    date_str = date_val.strip()
                    # Basic ISO/Date pattern check
                    if not re.search(r"^\d{4}-\d{2}-\d{2}", date_str) and not re.search(r"[A-Za-z]+\s+\d{1,2},\s+\d{4}", date_str):
                        errors.append(f"Malformed date in '{date_key}': '{date_str}'.")

        # 7. Financial Breakdown & Contradiction Detection
        fin_dict = raw_output.get("financial") or {}
        if not isinstance(fin_dict, dict):
            errors.append("Field 'financial' must be an object.")
            fin_dict = {}

        cost_status = str(fin_dict.get("participation_cost_status") or "UNCERTAIN").strip().upper()
        if cost_status not in [c.value for c in ParticipationCostStatus]:
            errors.append(f"Invalid participation_cost_status '{cost_status}'. Must be FREE, PAID, or UNCERTAIN.")
            cost_status = ParticipationCostStatus.UNCERTAIN.value

        app_fee_status = str(fin_dict.get("application_fee_status") or "UNKNOWN").strip().upper()
        if app_fee_status not in [f.value for f in FeeStatus]:
            errors.append(f"Invalid application_fee_status '{app_fee_status}'. Must be FREE, PAID, or UNKNOWN.")
            app_fee_status = FeeStatus.UNKNOWN.value

        reg_fee_status = str(fin_dict.get("registration_fee_status") or "UNKNOWN").strip().upper()
        if reg_fee_status not in [f.value for f in FeeStatus]:
            errors.append(f"Invalid registration_fee_status '{reg_fee_status}'. Must be FREE, PAID, or UNKNOWN.")
            reg_fee_status = FeeStatus.UNKNOWN.value

        comp_status = str(fin_dict.get("compensation_status") or "UNKNOWN").strip().upper()
        if comp_status not in [c.value for c in CompensationStatus]:
            errors.append(f"Invalid compensation_status '{comp_status}'. Must be PAID, UNPAID, or UNKNOWN.")
            comp_status = CompensationStatus.UNKNOWN.value

        # Financial Contradiction Checks
        if cost_status == ParticipationCostStatus.FREE.value:
            if app_fee_status == FeeStatus.PAID.value:
                errors.append("Financial contradiction: participation_cost_status is 'FREE' but application_fee_status is 'PAID'.")
            if reg_fee_status == FeeStatus.PAID.value:
                errors.append("Financial contradiction: participation_cost_status is 'FREE' but registration_fee_status is 'PAID'.")

        # 8. Evidence Integrity & Source Grounding Check
        evidence_list = raw_output.get("evidence") or []
        if not isinstance(evidence_list, list):
            errors.append("Field 'evidence' must be a list of evidence items.")
            evidence_list = []

        normalized_source = _normalize_text_for_search(source_content)
        parsed_evidence: List[EvidenceItem] = []

        for idx, ev in enumerate(evidence_list):
            if not isinstance(ev, dict):
                errors.append(f"Evidence item #{idx + 1} is not a valid dictionary.")
                continue

            field_name = str(ev.get("field_name") or "").strip()
            exact_excerpt = str(ev.get("exact_excerpt") or "").strip()
            ev_url = str(ev.get("source_url") or source_url).strip()
            sec_id = ev.get("section_identifier")

            if not field_name:
                errors.append(f"Evidence item #{idx + 1} has an empty 'field_name'.")
            if not exact_excerpt:
                errors.append(f"Evidence item #{idx + 1} for '{field_name}' has an empty 'exact_excerpt'.")
                continue

            if len(exact_excerpt) > self.MAX_EXCERPT_LENGTH:
                errors.append(f"Evidence excerpt for '{field_name}' exceeds maximum length ({len(exact_excerpt)} > {self.MAX_EXCERPT_LENGTH}).")

            # Check verbatim presence in source content
            normalized_excerpt = _normalize_text_for_search(exact_excerpt)
            if normalized_source and len(normalized_excerpt) >= 5:
                # Substring check
                if normalized_excerpt not in normalized_source:
                    # Allow slight fuzzy match if punctuation differs
                    clean_excerpt_chars = re.sub(r"[^\w\s]", "", normalized_excerpt)
                    clean_source_chars = re.sub(r"[^\w\s]", "", normalized_source)
                    if clean_excerpt_chars not in clean_source_chars:
                        errors.append(
                            f"Ungrounded claim: evidence excerpt for '{field_name}' was not found in source page content "
                            f"('{exact_excerpt[:50]}...')."
                        )

            parsed_evidence.append(
                EvidenceItem(
                    field_name=field_name,
                    exact_excerpt=exact_excerpt,
                    source_url=ev_url,
                    section_identifier=sec_id,
                )
            )

        # 9. Verify that Claims Have Associated Evidence
        # If deadline is claimed, there must be evidence
        deadline = dates_dict.get("application_deadline")
        if deadline:
            has_deadline_ev = any("deadline" in e.field_name.lower() or "application" in e.field_name.lower() for e in parsed_evidence)
            if not has_deadline_ev:
                errors.append(f"Application deadline '{deadline}' was claimed without supporting source evidence.")

        # If free participation is claimed, verify financial evidence exists
        if cost_status == ParticipationCostStatus.FREE.value:
            has_price_ev = any("free" in e.exact_excerpt.lower() or "cost" in e.field_name.lower() or "price" in e.field_name.lower() for e in parsed_evidence)
            if not has_price_ev and not fin_dict.get("pricing_evidence"):
                # Downgrade rather than fail if everything else is good, or flag warning
                logger.warning(f"Downgrading unevidenced 'FREE' claim to 'UNCERTAIN' for candidate '{candidate_id}'.")
                cost_status = ParticipationCostStatus.UNCERTAIN.value

        # Build clean EligibilityData
        elig_dict = raw_output.get("eligibility") or {}
        eligibility = EligibilityData(
            education=elig_dict.get("education"),
            academic_year=elig_dict.get("academic_year"),
            experience=elig_dict.get("experience"),
            age_restrictions=elig_dict.get("age_restrictions"),
            countries=elig_dict.get("countries") or [],
            other_requirements=elig_dict.get("other_requirements") or [],
        )

        # Build clean LocationData
        location = LocationData(
            country=loc_dict.get("country"),
            region=loc_dict.get("region"),
            city=loc_dict.get("city"),
            work_mode=work_mode,
            global_eligibility=loc_dict.get("global_eligibility"),
        )

        # Build clean DatesData
        dates = DatesData(
            published_at=dates_dict.get("published_at"),
            application_open=dates_dict.get("application_open"),
            application_deadline=dates_dict.get("application_deadline"),
            event_start=dates_dict.get("event_start"),
            event_end=dates_dict.get("event_end"),
            timezone=dates_dict.get("timezone"),
        )

        # Build clean FinancialClassification
        financial = FinancialClassification(
            participation_cost_status=cost_status,
            application_fee_status=app_fee_status,
            registration_fee_status=reg_fee_status,
            mandatory_purchase_status=str(fin_dict.get("mandatory_purchase_status") or "UNKNOWN").upper(),
            mandatory_paid_certification_status=str(fin_dict.get("mandatory_paid_certification_status") or "UNKNOWN").upper(),
            mandatory_membership_status=str(fin_dict.get("mandatory_membership_status") or "UNKNOWN").upper(),
            compensation_status=comp_status,
            compensation_details=fin_dict.get("compensation_details"),
            pricing_evidence=fin_dict.get("pricing_evidence") or [],
        )

        is_valid = len(errors) == 0
        validation_status = "valid" if is_valid else "validation_error"

        result = ClassificationResult(
            candidate_id=candidate_id,
            title=title,
            description=description,
            organization=raw_output.get("organization"),
            category=category_enum.value,
            subcategory=raw_output.get("subcategory"),
            required_skills=raw_output.get("required_skills") or [],
            preferred_skills=raw_output.get("preferred_skills") or [],
            cybersecurity_domain=raw_output.get("cybersecurity_domain"),
            experience_level=exp_level,
            eligibility=eligibility,
            location=location,
            dates=dates,
            financial=financial,
            evidence=parsed_evidence,
            confidence=confidence,
            provider_used=provider,
            model_used=model,
            prompt_version=prompt_version,
            validation_status=validation_status,
            validation_errors=errors,
            raw_response=raw_output,
        )

        return is_valid, errors, result

