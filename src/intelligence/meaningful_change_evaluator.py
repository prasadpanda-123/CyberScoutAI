"""
Meaningful Change Evaluator for CyberScout AI (Phase 7).

Determines whether an opportunity update represents an actionable change
deserving of a user notification, versus volatile or bookkeeping changes
(e.g., harvest timestamps, scraper runs, whitespace formatting).
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.models.notification_models import MeaningfulChangeDTO
from src.models.opportunity import Opportunity


class MeaningfulChangeEvaluator:
    """
    Evaluates changes between an existing database opportunity and an incoming candidate.
    Produces deterministic change fingerprints and actionable change determinations.
    """

    # Substantive, actionable fields that impact user decision making
    ACTIONABLE_FIELDS = (
        "title",
        "description",
        "deadline",
        "price_amount",
        "stipend_amount",
        "pricing_type",
        "stipend_type",
        "remote",
        "location",
        "eligibility",
        "requirements",
        "tags",
        "certificate",
        "category",
        "opportunity_type",
    )

    # Volatile/bookkeeping fields that must NEVER trigger an update alert
    VOLATILE_FIELDS = (
        "last_seen",
        "last_seen_at",
        "last_harvested_at",
        "last_changed_at",
        "discovered_date",
        "first_seen_at",
        "run_id",
        "url_hash",
        "raw_data",
        "freshness_score",
        "provider_score",
        "confidence_score",
        "quality_score",
        "spam_score",
        "topic_score",
        "keyword_score",
    )

    @classmethod
    def _normalize_text(cls, text: Optional[str]) -> str:
        """Normalizes text by collapsing whitespace and stripping edges."""
        if not text:
            return ""
        # Collapse multiple whitespace characters/newlines into a single space
        return re.sub(r"\s+", " ", str(text)).strip()

    @classmethod
    def _normalize_tags(cls, tags: Any) -> List[str]:
        """Normalizes tags into sorted unique lowercase tokens."""
        if not tags:
            return []
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = tags.split(",")
        if isinstance(tags, (list, set, tuple)):
            clean = {str(t).strip().lower() for t in tags if str(t).strip()}
            return sorted(list(clean))
        return []

    @classmethod
    def _normalize_date(cls, val: Any) -> str:
        """Normalizes date/deadline to ISO YYYY-MM-DD string."""
        if val is None:
            return ""
        if hasattr(val, "isoformat"):
            return val.isoformat()[:10]
        s = str(val).strip()
        return s[:10] if len(s) >= 10 else s

    @classmethod
    def compute_fingerprint(cls, opp: Opportunity) -> str:
        """
        Computes a deterministic SHA-256 fingerprint of the actionable fields of an Opportunity.
        Does NOT include any volatile or timestamp fields.
        """
        data = {
            "title": cls._normalize_text(opp.title),
            "description": cls._normalize_text(opp.description)[:300],  # sample core desc
            "deadline": cls._normalize_date(opp.deadline),
            "price_amount": opp.price_amount if opp.price_amount is not None else 0.0,
            "stipend_amount": opp.stipend_amount if opp.stipend_amount is not None else 0.0,
            "pricing_type": str(opp.pricing_type or "").lower().strip(),
            "stipend_type": str(opp.stipend_type or "").lower().strip(),
            "remote": bool(opp.remote),
            "location": cls._normalize_text(opp.location),
            "eligibility": cls._normalize_text(opp.eligibility),
            "requirements": cls._normalize_text(opp.requirements),
            "tags": cls._normalize_tags(opp.tags),
            "certificate": bool(opp.certificate),
            "category": str(opp.category or "").lower().strip(),
            "opportunity_type": str(opp.opportunity_type or "").lower().strip(),
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def evaluate(
        cls, candidate: Opportunity, existing: Optional[Opportunity]
    ) -> MeaningfulChangeDTO:
        """
        Evaluates candidate against existing opportunity to determine if actionable changes occurred.
        """
        if not existing:
            cand_fp = cls.compute_fingerprint(candidate)
            return MeaningfulChangeDTO(
                is_meaningful=True,
                changed_fields=["all"],
                change_fingerprint=cand_fp,
                summary="New opportunity created",
            )

        changed_fields: List[str] = []

        # 1. Title
        if cls._normalize_text(candidate.title) != cls._normalize_text(existing.title):
            changed_fields.append("title")

        # 2. Description (significant textual change)
        cand_desc = cls._normalize_text(candidate.description)
        exist_desc = cls._normalize_text(existing.description)
        if cand_desc != exist_desc:
            # Check if it's more than trivial whitespace difference
            if abs(len(cand_desc) - len(exist_desc)) > 10 or cand_desc[:100] != exist_desc[:100]:
                changed_fields.append("description")

        # 3. Deadline
        if cls._normalize_date(candidate.deadline) != cls._normalize_date(existing.deadline):
            changed_fields.append("deadline")

        # 4. Economic / Financial parameters
        if candidate.price_amount != existing.price_amount:
            changed_fields.append("price_amount")
        if candidate.stipend_amount != existing.stipend_amount:
            changed_fields.append("stipend_amount")
        if (candidate.pricing_type or "").lower() != (existing.pricing_type or "").lower():
            changed_fields.append("pricing_type")
        if (candidate.stipend_type or "").lower() != (existing.stipend_type or "").lower():
            changed_fields.append("stipend_type")

        # 5. Modality & Location
        if candidate.remote != existing.remote:
            changed_fields.append("remote")
        if cls._normalize_text(candidate.location) != cls._normalize_text(existing.location):
            changed_fields.append("location")

        # 6. Certification & Eligibility
        if candidate.certificate != existing.certificate:
            changed_fields.append("certificate")
        if cls._normalize_text(candidate.eligibility) != cls._normalize_text(existing.eligibility):
            changed_fields.append("eligibility")
        if cls._normalize_text(candidate.requirements) != cls._normalize_text(existing.requirements):
            changed_fields.append("requirements")

        # 7. Taxonomy & Skills
        if cls._normalize_tags(candidate.tags) != cls._normalize_tags(existing.tags):
            changed_fields.append("tags")
        if (candidate.category or "").lower() != (existing.category or "").lower():
            changed_fields.append("category")
        if (candidate.opportunity_type or "").lower() != (existing.opportunity_type or "").lower():
            changed_fields.append("opportunity_type")

        cand_fp = cls.compute_fingerprint(candidate)
        is_meaningful = len(changed_fields) > 0

        summary = (
            f"Changed: {', '.join(changed_fields)}"
            if is_meaningful
            else "No substantive changes"
        )

        return MeaningfulChangeDTO(
            is_meaningful=is_meaningful,
            changed_fields=changed_fields,
            change_fingerprint=cand_fp,
            summary=summary,
        )
