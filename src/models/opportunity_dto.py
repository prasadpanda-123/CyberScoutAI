"""
Normalized Opportunity Data Transfer Object (DTO) for CyberScout AI.

Serves as the canonical intermediate representation produced by all collectors
prior to pipeline processing, deduplication, scoring, and persistence.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.models.enums import (
    CertificateAvailable,
    CertificateCost,
    Difficulty,
    OpportunityCategory,
    OpportunityType,
    PricingType,
    Status,
    StipendType,
)
from src.models.opportunity import Opportunity
from src.utils.url_utils import normalize_url


@dataclass
class NormalizedOpportunityDTO:
    """
    Standardized intermediate opportunity representation returned by all collectors.
    """

    title: str
    url: str
    source_id: str
    source_external_id: Optional[str] = None
    canonical_url: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    opportunity_type: str = OpportunityType.INTERNSHIP.value
    categories: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    location: Optional[str] = None
    remote: bool = False
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    duration: Optional[str] = None
    difficulty: str = Difficulty.UNKNOWN.value

    # Granular Pricing Model
    pricing_type: str = PricingType.UNKNOWN.value
    price_amount: Optional[float] = None
    currency: Optional[str] = None
    application_fee: Optional[float] = None
    certificate_fee: Optional[float] = None
    is_free: Optional[bool] = None
    free_conditions: Optional[str] = None

    # Granular Stipend Model
    stipend_type: str = StipendType.UNKNOWN.value
    stipend_amount: Optional[float] = None
    stipend_currency: Optional[str] = None

    # Granular Certificate Model
    certificate_available: str = CertificateAvailable.UNKNOWN.value
    certificate_cost: str = CertificateCost.UNKNOWN.value

    # Qualification & Content
    eligibility: Optional[str] = None
    requirements: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Provenance
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        if not self.canonical_url and self.url:
            self.canonical_url = normalize_url(self.url)

        # Infer is_free flag from pricing_type if unspecified
        if self.is_free is None:
            if self.pricing_type == PricingType.FREE.value:
                self.is_free = True
            elif self.pricing_type == PricingType.PAID.value:
                self.is_free = False

    def to_dict(self) -> Dict[str, Any]:
        """Converts DTO to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizedOpportunityDTO":
        """Constructs DTO from dictionary, ignoring extraneous keys."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_opportunity(self) -> Opportunity:
        """
        Converts NormalizedOpportunityDTO to canonical Opportunity domain model,
        preserving complete backward compatibility with pipeline stages.
        """
        # Determine backward-compatible paid boolean
        paid_bool: Optional[bool] = None
        if self.pricing_type == PricingType.PAID.value or self.is_free is False:
            paid_bool = True
        elif self.pricing_type == PricingType.FREE.value or self.is_free is True:
            paid_bool = False

        # Determine certificate boolean
        has_certificate = self.certificate_available == CertificateAvailable.YES.value

        # Map opportunity_type or category to OpportunityCategory
        mapped_cat = OpportunityCategory.OTHER.value
        opp_type_val = (self.opportunity_type or "").lower().strip()
        for cat in OpportunityCategory:
            if opp_type_val == cat.value:
                mapped_cat = cat.value
                break
        if mapped_cat == OpportunityCategory.OTHER.value and self.categories:
            for cat_candidate in self.categories:
                for cat in OpportunityCategory:
                    if cat_candidate.lower() == cat.value:
                        mapped_cat = cat.value
                        break

        # Build raw_data payload containing DTO extensions
        raw = dict(self.raw_payload) if self.raw_payload else {}
        raw["pricing_type"] = self.pricing_type
        raw["price_amount"] = self.price_amount
        raw["application_fee"] = self.application_fee
        raw["certificate_fee"] = self.certificate_fee
        raw["is_free"] = self.is_free
        raw["free_conditions"] = self.free_conditions
        raw["stipend_type"] = self.stipend_type
        raw["stipend_amount"] = self.stipend_amount
        raw["stipend_currency"] = self.stipend_currency
        raw["certificate_available"] = self.certificate_available
        raw["certificate_cost"] = self.certificate_cost
        raw["eligibility"] = self.eligibility
        raw["requirements"] = self.requirements
        raw["opportunity_type"] = self.opportunity_type
        raw["canonical_url"] = self.canonical_url

        opp = Opportunity(
            title=self.title,
            url=self.canonical_url or self.url,
            source_id=self.source_id,
            description=self.description,
            category=mapped_cat,
            provider=self.provider,
            company=self.provider,
            location=self.location,
            remote=self.remote,
            paid=paid_bool,
            certificate=has_certificate,
            price_raw=f"{self.currency or ''} {self.price_amount}".strip() if self.price_amount is not None else None,
            price_normalized=str(self.price_amount) if self.price_amount is not None else None,
            currency=self.currency,
            deadline=self.deadline,
            duration=self.duration,
            difficulty=self.difficulty,
            tags=list(set(self.tags + self.skills + self.categories)),
            raw_data=raw,
            status=Status.ACTIVE.value,
            source_external_id=self.source_external_id,
            canonical_url=self.canonical_url,
        )

        # Attach granular attributes if supported by Opportunity model
        if hasattr(opp, "opportunity_type"):
            opp.opportunity_type = self.opportunity_type
        if hasattr(opp, "pricing_type"):
            opp.pricing_type = self.pricing_type
        if hasattr(opp, "price_amount"):
            opp.price_amount = self.price_amount
        if hasattr(opp, "application_fee"):
            opp.application_fee = self.application_fee
        if hasattr(opp, "certificate_fee"):
            opp.certificate_fee = self.certificate_fee
        if hasattr(opp, "is_free"):
            opp.is_free = self.is_free
        if hasattr(opp, "free_conditions"):
            opp.free_conditions = self.free_conditions
        if hasattr(opp, "stipend_type"):
            opp.stipend_type = self.stipend_type
        if hasattr(opp, "stipend_amount"):
            opp.stipend_amount = self.stipend_amount
        if hasattr(opp, "stipend_currency"):
            opp.stipend_currency = self.stipend_currency
        if hasattr(opp, "certificate_available"):
            opp.certificate_available = self.certificate_available
        if hasattr(opp, "certificate_cost"):
            opp.certificate_cost = self.certificate_cost
        if hasattr(opp, "eligibility"):
            opp.eligibility = self.eligibility
        if hasattr(opp, "requirements"):
            opp.requirements = ", ".join(self.requirements) if isinstance(self.requirements, list) else str(self.requirements or "")

        return opp

