"""
Domain Models, Enums, and Dataclasses for AI Opportunity Classification (Phase D).

Defines canonical data structures for Groq (Primary) and Google Gemini (Fallback)
classification engines, strict JSON schema representations, and telemetry metrics.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ClassificationCategory(str, Enum):
    """Authoritative taxonomy of 16 cybersecurity opportunity categories."""

    JOB = "job"
    INTERNSHIP = "internship"
    BUG_BOUNTY = "bug_bounty"
    VULNERABILITY_DISCLOSURE = "vulnerability_disclosure"
    CTF = "ctf"
    HACKATHON = "hackathon"
    SCHOLARSHIP = "scholarship"
    FREE_COURSE = "free_course"
    FREE_TRAINING = "free_training"
    RESEARCH_OPPORTUNITY = "research_opportunity"
    CONFERENCE = "conference"
    WEBINAR = "webinar"
    DFIR = "dfir"
    OPEN_SOURCE_CONTRIBUTION = "open_source_contribution"
    MENTORSHIP = "mentorship"
    OTHER = "other"

    @classmethod
    def normalize(cls, val: str) -> "ClassificationCategory":
        """Normalizes variations into canonical enum value."""
        if not val:
            return cls.OTHER
        clean = val.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "vdp": cls.VULNERABILITY_DISCLOSURE,
            "vulnerability_disclosure_program": cls.VULNERABILITY_DISCLOSURE,
            "course": cls.FREE_COURSE,
            "course_certification": cls.FREE_COURSE,
            "training": cls.FREE_TRAINING,
            "research": cls.RESEARCH_OPPORTUNITY,
            "workshop": cls.WEBINAR,
            "workshop_webinar": cls.WEBINAR,
            "dfir_challenge": cls.DFIR,
            "forensics": cls.DFIR,
            "open_source": cls.OPEN_SOURCE_CONTRIBUTION,
            "open_source_program": cls.OPEN_SOURCE_CONTRIBUTION,
            "security_mentorship": cls.MENTORSHIP,
        }
        if clean in aliases:
            return aliases[clean]
        for member in cls:
            if member.value == clean:
                return member
        return cls.OTHER


class ExperienceLevel(str, Enum):
    """Target candidate professional experience tier."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ALL_LEVELS = "all_levels"
    UNKNOWN = "unknown"


class WorkMode(str, Enum):
    """Physical work arrangement."""

    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class ParticipationCostStatus(str, Enum):
    """
    Economic participation classification.
    Zero-trust rule: default is always UNCERTAIN until verified.
    """

    FREE = "FREE"
    PAID = "PAID"
    UNCERTAIN = "UNCERTAIN"


class FeeStatus(str, Enum):
    """Fine-grained assessment of specific fee mechanisms."""

    FREE = "FREE"
    PAID = "PAID"
    UNKNOWN = "UNKNOWN"


class CompensationStatus(str, Enum):
    """Compensation or prize status for the applicant."""

    PAID = "PAID"        # Pays salary, stipend, or cash prizes
    UNPAID = "UNPAID"    # Explicitly volunteer or unpaid
    UNKNOWN = "UNKNOWN"  # Not stated in source


@dataclass
class EligibilityData:
    """Structured eligibility constraints extracted with evidence."""

    education: Optional[str] = None
    academic_year: Optional[str] = None
    experience: Optional[str] = None
    age_restrictions: Optional[str] = None
    countries: List[str] = field(default_factory=list)
    other_requirements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LocationData:
    """Geographic parameters and workplace arrangement."""

    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    work_mode: str = WorkMode.UNKNOWN.value
    global_eligibility: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DatesData:
    """Key temporal milestones."""

    published_at: Optional[str] = None
    application_open: Optional[str] = None
    application_deadline: Optional[str] = None
    event_start: Optional[str] = None
    event_end: Optional[str] = None
    timezone: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinancialClassification:
    """
    Detailed economic breakdown.
    
    Critical distinction:
    - An internship or job that pays a salary is still free to apply for.
    - A CTF with cash prizes has compensation_status='PAID' but participation_cost_status='FREE'.
    - Courses requiring mandatory payment for certificates are NOT completely free.
    """

    participation_cost_status: str = ParticipationCostStatus.UNCERTAIN.value
    application_fee_status: str = FeeStatus.UNKNOWN.value
    registration_fee_status: str = FeeStatus.UNKNOWN.value
    mandatory_purchase_status: str = FeeStatus.UNKNOWN.value
    mandatory_paid_certification_status: str = FeeStatus.UNKNOWN.value
    mandatory_membership_status: str = FeeStatus.UNKNOWN.value
    compensation_status: str = CompensationStatus.UNKNOWN.value
    compensation_details: Optional[str] = None
    pricing_evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceItem:
    """Verbatim citation linking a structured claim to the source page text."""

    field_name: str
    exact_excerpt: str
    source_url: str
    section_identifier: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationResult:
    """
    Validated opportunity classification record output by the AI engine.
    
    Derived strictly from page evidence without hallucination or invented facts.
    Missing fields remain None or explicit UNKNOWN states.
    """

    candidate_id: str
    title: str
    description: str
    organization: Optional[str] = None
    category: str = ClassificationCategory.OTHER.value
    subcategory: Optional[str] = None
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    cybersecurity_domain: Optional[str] = None
    experience_level: str = ExperienceLevel.UNKNOWN.value
    eligibility: EligibilityData = field(default_factory=EligibilityData)
    location: LocationData = field(default_factory=LocationData)
    dates: DatesData = field(default_factory=DatesData)
    financial: FinancialClassification = field(default_factory=FinancialClassification)
    evidence: List[EvidenceItem] = field(default_factory=list)
    confidence: float = 0.0
    provider_used: str = ""   # 'groq' or 'gemini'
    model_used: str = ""
    prompt_version: str = "v1.0"
    classified_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    validation_status: str = "valid"  # 'valid', 'unsupported_claims', 'malformed', 'schema_error'
    validation_errors: List[str] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": self.title,
            "description": self.description,
            "organization": self.organization,
            "category": self.category,
            "subcategory": self.subcategory,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "cybersecurity_domain": self.cybersecurity_domain,
            "experience_level": self.experience_level,
            "eligibility": self.eligibility.to_dict(),
            "location": self.location.to_dict(),
            "dates": self.dates.to_dict(),
            "financial": self.financial.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence,
            "provider_used": self.provider_used,
            "model_used": self.model_used,
            "prompt_version": self.prompt_version,
            "classified_at": self.classified_at,
            "validation_status": self.validation_status,
            "validation_errors": self.validation_errors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClassificationResult":
        """Instantiates ClassificationResult safely handling nested dataclasses."""
        elig_data = data.get("eligibility", {})
        elig = EligibilityData(**elig_data) if isinstance(elig_data, dict) else EligibilityData()

        loc_data = data.get("location", {})
        loc = LocationData(**loc_data) if isinstance(loc_data, dict) else LocationData()

        dates_data = data.get("dates", {})
        dt = DatesData(**dates_data) if isinstance(dates_data, dict) else DatesData()

        fin_data = data.get("financial", {})
        fin = FinancialClassification(**fin_data) if isinstance(fin_data, dict) else FinancialClassification()

        ev_list = data.get("evidence", []) or []
        evidence_items = []
        for e in ev_list:
            if isinstance(e, dict):
                evidence_items.append(EvidenceItem(**e))
            elif isinstance(e, EvidenceItem):
                evidence_items.append(e)

        return cls(
            candidate_id=data.get("candidate_id", ""),
            title=data.get("title", "Untitled Opportunity"),
            description=data.get("description", ""),
            organization=data.get("organization"),
            category=data.get("category", ClassificationCategory.OTHER.value),
            subcategory=data.get("subcategory"),
            required_skills=data.get("required_skills") or [],
            preferred_skills=data.get("preferred_skills") or [],
            cybersecurity_domain=data.get("cybersecurity_domain"),
            experience_level=data.get("experience_level", ExperienceLevel.UNKNOWN.value),
            eligibility=elig,
            location=loc,
            dates=dt,
            financial=fin,
            evidence=evidence_items,
            confidence=float(data.get("confidence") or 0.0),
            provider_used=data.get("provider_used", ""),
            model_used=data.get("model_used", ""),
            prompt_version=data.get("prompt_version", "v1.0"),
            classified_at=data.get("classified_at", datetime.now(timezone.utc).isoformat()),
            validation_status=data.get("validation_status", "valid"),
            validation_errors=data.get("validation_errors") or [],
            raw_response=data.get("raw_response", {}),
        )


@dataclass
class ClassificationBudget:
    """Configurable usage limits and cost guardrails for AI classification providers."""

    max_classifications_per_run: int = 25
    daily_limit: int = 100
    timeout_seconds: float = 30.0
    max_retries: int = 2
    backoff_factor: float = 1.5
    max_tokens: int = 4096

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationRunSummary:
    """Summary metrics and audit record for an executed AI classification run."""

    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    candidates_attempted: int = 0
    candidates_classified_groq: int = 0
    candidates_classified_gemini: int = 0
    candidates_failed: int = 0
    candidates_rejected_validation: int = 0
    candidates_skipped: int = 0
    status: str = "completed"
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIProviderMetrics:
    """Telemetry tracking for individual AI classification providers."""

    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limits_encountered: int = 0
    total_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    last_request_at: Optional[str] = None
    last_error: Optional[str] = None

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return round(self.total_latency_ms / self.successful_requests, 2)

    def record_success(self, latency_ms: float, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_ms += latency_ms
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.last_request_at = datetime.now(timezone.utc).isoformat()

    def record_failure(self, error_msg: str, is_rate_limit: bool = False) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        if is_rate_limit:
            self.rate_limits_encountered += 1
        self.last_error = error_msg
        self.last_request_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limits_encountered": self.rate_limits_encountered,
            "avg_latency_ms": self.avg_latency_ms,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "last_request_at": self.last_request_at,
            "last_error": self.last_error,
        }

