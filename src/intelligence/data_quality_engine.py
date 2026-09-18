"""
Authoritative Data Quality Engine for CyberScout AI (Phase 6).

Executes deterministic, explainable, bounded data quality checks across completeness,
validity, and contradiction detection to isolate corrupt data into QUARANTINE.
"""

from datetime import date, datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.core.logging import get_logger
from src.models.data_quality_models import ValidationResultDTO
from src.models.enums import LifecycleStatus, QualityStatus
from src.models.opportunity import Opportunity

logger = get_logger(__name__)

# Dangerous URL protocols strictly forbidden
DANGEROUS_PROTOCOLS = {"javascript:", "data:", "file:", "vbscript:", "blob:"}

# Known enum sets for strict validity checking
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced", "unknown"}
VALID_PRICING_TYPES = {"free", "paid", "freemium", "unknown"}
VALID_STIPEND_TYPES = {"none", "unpaid", "paid", "performance_based", "expenses_covered", "unknown"}
VALID_CATEGORIES = {
    "internship", "job", "course", "certification", "scholarship",
    "hackathon", "ctf", "github_repository", "security_tool",
    "security_news", "blog", "tutorial", "research_paper", "other"
}


class DataQualityEngine:
    """
    Deterministic data quality gate inspecting every opportunity before persistence,
    ranking, or user notification.
    """

    def __init__(self):
        pass

    def evaluate(self, opp: Opportunity) -> ValidationResultDTO:
        """
        Evaluates an Opportunity model for completeness, validity, and contradictions.

        Returns:
            ValidationResultDTO containing quality status, completeness score,
            quarantine reason (if any), and diagnostic details.
        """
        missing_fields: List[str] = []
        field_errors: Dict[str, str] = {}
        contradictions: List[str] = []

        # -------------------------------------------------------------
        # 1. COMPLETENESS EVALUATION
        # -------------------------------------------------------------
        # Required fields (critical gate)
        if not opp.title or not str(opp.title).strip():
            missing_fields.append("title")
            field_errors["title"] = "Title is required and non-empty."

        if not opp.url or not str(opp.url).strip():
            missing_fields.append("url")
            field_errors["url"] = "URL is required and non-empty."

        if not opp.source_id or not str(opp.source_id).strip():
            missing_fields.append("source_id")
            field_errors["source_id"] = "Source ID is required and non-empty."

        # Compute granular completeness score
        score = 1.0

        # Penalize for missing important fields
        if not opp.description or not str(opp.description).strip():
            missing_fields.append("description")
            score -= 0.15
        if not opp.category or opp.category == "other":
            score -= 0.10
        if not opp.opportunity_type:
            score -= 0.10

        # Minor penalty for missing optional fields
        if not opp.tags or len(opp.tags) == 0:
            score -= 0.05
        if opp.price_amount is None and getattr(opp, "pricing_type", "unknown") == "unknown":
            score -= 0.05
        if not opp.location and not opp.remote:
            score -= 0.05

        completeness_score = max(0.0, min(1.0, score))

        # Critical failure: missing required field -> instant Quarantine
        if "title" in missing_fields or "url" in missing_fields or "source_id" in missing_fields:
            return ValidationResultDTO(
                is_valid=False,
                quality_status=QualityStatus.QUARANTINED,
                completeness_score=completeness_score,
                quarantine_reason=f"MISSING_REQUIRED_FIELDS: {', '.join([f for f in missing_fields if f in ('title', 'url', 'source_id')])}",
                missing_fields=missing_fields,
                contradictions=contradictions,
                field_errors=field_errors,
            )

        # -------------------------------------------------------------
        # 2. VALIDITY CHECKS
        # -------------------------------------------------------------
        clean_title = str(opp.title).strip()
        if len(clean_title) < 3:
            field_errors["title"] = f"Title is suspiciously short ({len(clean_title)} chars)."
        elif len(clean_title) > 500:
            field_errors["title"] = f"Title exceeds maximum length ({len(clean_title)} chars)."
        elif re.search(r"<\s*script|javascript:|data:text/html", clean_title, re.I):
            field_errors["title"] = "Title contains dangerous script or HTML tags."

        # URL validation
        clean_url = str(opp.url).strip()
        lower_url = clean_url.lower()
        if any(lower_url.startswith(p) for p in DANGEROUS_PROTOCOLS):
            field_errors["url"] = f"URL uses forbidden dangerous pseudo-protocol."
        else:
            try:
                parsed = urlparse(clean_url)
                if parsed.scheme not in ("http", "https"):
                    field_errors["url"] = f"Invalid URL scheme '{parsed.scheme}'. Must be HTTP or HTTPS."
                elif not parsed.netloc or "." not in parsed.netloc:
                    field_errors["url"] = f"Invalid URL hostname '{parsed.netloc}'."
            except Exception as ue:
                field_errors["url"] = f"Malformed URL: {ue}"

        # Date validations
        pub_date: Optional[date] = None
        if opp.published_date:
            pub_str = str(opp.published_date).strip()
            try:
                pub_date = datetime.strptime(pub_str[:10], "%Y-%m-%d").date()
                if pub_date.year < 2000 or pub_date.year > 2100:
                    field_errors["published_date"] = f"Published date year out of sensible range ({pub_date.year})."
            except Exception:
                field_errors["published_date"] = f"Published date '{pub_str}' is malformed."

        deadline_date: Optional[date] = None
        if opp.deadline:
            dl_str = str(opp.deadline).strip()
            try:
                deadline_date = datetime.strptime(dl_str[:10], "%Y-%m-%d").date()
                if deadline_date.year < 2000 or deadline_date.year > 2100:
                    field_errors["deadline"] = f"Deadline year out of sensible range ({deadline_date.year})."
            except Exception:
                field_errors["deadline"] = f"Deadline '{dl_str}' is malformed."

        # Economic validations
        if opp.price_amount is not None:
            try:
                val = float(opp.price_amount)
                if val < 0.0:
                    field_errors["price_amount"] = f"Price cannot be negative ({val})."
            except (ValueError, TypeError):
                field_errors["price_amount"] = f"Price amount '{opp.price_amount}' is not a valid number."

        if opp.stipend_amount is not None:
            try:
                val = float(opp.stipend_amount)
                if val < 0.0:
                    field_errors["stipend_amount"] = f"Stipend cannot be negative ({val})."
            except (ValueError, TypeError):
                field_errors["stipend_amount"] = f"Stipend amount '{opp.stipend_amount}' is not a valid number."

        if opp.application_fee is not None:
            try:
                val = float(opp.application_fee)
                if val < 0.0:
                    field_errors["application_fee"] = f"Application fee cannot be negative ({val})."
            except (ValueError, TypeError):
                field_errors["application_fee"] = f"Application fee '{opp.application_fee}' is not a valid number."

        # Enum validations
        if opp.difficulty and str(opp.difficulty).lower() not in VALID_DIFFICULTIES:
            field_errors["difficulty"] = f"Unknown difficulty level '{opp.difficulty}'."

        if opp.pricing_type and str(opp.pricing_type).lower() not in VALID_PRICING_TYPES:
            field_errors["pricing_type"] = f"Unknown pricing type '{opp.pricing_type}'."

        if opp.stipend_type and str(opp.stipend_type).lower() not in VALID_STIPEND_TYPES:
            field_errors["stipend_type"] = f"Unknown stipend type '{opp.stipend_type}'."

        # -------------------------------------------------------------
        # 3. CONTRADICTION DETECTION
        # -------------------------------------------------------------
        # 3.1 Free vs Fee Contradiction
        if opp.is_free is True:
            if opp.price_amount is not None and float(opp.price_amount) > 0.0:
                contradictions.append(f"is_free=True but price_amount={opp.price_amount}")
            if opp.application_fee is not None and float(opp.application_fee) > 0.0:
                contradictions.append(f"is_free=True but application_fee={opp.application_fee}")

        # 3.2 Stipend Type None/Unpaid vs Stipend Amount > 0
        if opp.stipend_type and str(opp.stipend_type).lower() in ("none", "unpaid"):
            if opp.stipend_amount is not None and float(opp.stipend_amount) > 0.0:
                contradictions.append(f"stipend_type='{opp.stipend_type}' but stipend_amount={opp.stipend_amount}")

        # 3.3 Temporal Contradiction: Deadline before Published Date
        if pub_date and deadline_date and deadline_date < pub_date:
            contradictions.append(f"deadline ({deadline_date}) is earlier than published_date ({pub_date})")

        # 3.4 Remote Contradiction
        if opp.remote is False:
            loc_lower = (opp.location or "").lower().strip()
            if loc_lower == "remote" or loc_lower == "remote only":
                contradictions.append(f"remote=False but location is '{opp.location}'")

        # -------------------------------------------------------------
        # 4. DECISION & QUARANTINE ROUTING
        # -------------------------------------------------------------
        critical_errors = [k for k in field_errors.keys() if k in ("title", "url", "published_date", "deadline")]
        
        if contradictions or critical_errors:
            # Critical validation failure or contradiction -> QUARANTINE
            reasons = []
            if contradictions:
                reasons.append(f"CONTRADICTIONS: {'; '.join(contradictions)}")
            if critical_errors:
                reasons.append(f"CRITICAL_ERRORS: {'; '.join(f'{k}: {field_errors[k]}' for k in critical_errors)}")
            quarantine_msg = " | ".join(reasons)

            return ValidationResultDTO(
                is_valid=False,
                quality_status=QualityStatus.QUARANTINED,
                completeness_score=completeness_score,
                quarantine_reason=quarantine_msg,
                missing_fields=missing_fields,
                contradictions=contradictions,
                field_errors=field_errors,
            )

        if field_errors:
            # Non-critical errors (e.g. minor enum normalization needed) -> NEEDS_REVIEW
            return ValidationResultDTO(
                is_valid=True,
                quality_status=QualityStatus.NEEDS_REVIEW,
                completeness_score=completeness_score,
                quarantine_reason=None,
                missing_fields=missing_fields,
                contradictions=contradictions,
                field_errors=field_errors,
            )

        # Clean passed high-quality opportunity
        return ValidationResultDTO(
            is_valid=True,
            quality_status=QualityStatus.PASSED,
            completeness_score=completeness_score,
            quarantine_reason=None,
            missing_fields=missing_fields,
            contradictions=[],
            field_errors={},
        )
