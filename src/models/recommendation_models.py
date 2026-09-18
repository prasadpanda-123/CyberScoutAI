"""
Recommendation and Personalization Data Models for CyberScout AI.

Defines strongly-typed DTOs and Enums for eligibility evaluation,
feature scoring, ranking results, and human-readable recommendation explanations.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class EligibilityStatus(str, Enum):
    """Authoritative eligibility status for an opportunity relative to a user."""
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class EligibilityResult:
    """Represents the outcome of checking an opportunity's criteria against user profile."""
    status: EligibilityStatus = EligibilityStatus.UNKNOWN
    reasons: List[str] = field(default_factory=list)

    @property
    def is_eligible(self) -> bool:
        return self.status == EligibilityStatus.ELIGIBLE

    @property
    def is_ineligible(self) -> bool:
        return self.status == EligibilityStatus.INELIGIBLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reasons": self.reasons,
        }


@dataclass
class UserPreferencesDTO:
    """Explicit and structured user career/opportunity discovery preferences."""
    skills: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    preferred_categories: List[str] = field(default_factory=list)
    preferred_types: List[str] = field(default_factory=list)
    prefers_remote: Optional[bool] = None
    preferred_location: Optional[str] = None
    experience_level: Optional[str] = None  # 'beginner', 'intermediate', 'advanced'
    # Phase 7 Notification & Quiet Hours Preferences
    email_notifications_enabled: bool = True
    in_app_notifications_enabled: bool = True
    notify_new_opportunities: bool = True
    notify_meaningful_updates: bool = True
    notify_reopened_opportunities: bool = True
    delivery_mode: str = "digest"  # 'immediate', 'digest'
    digest_frequency: str = "daily"  # 'daily', 'weekly'
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    timezone: str = "UTC"
    min_score_threshold: float = 0.0

    def __post_init__(self):
        # Normalize skills and categories to lowercase stripped tokens
        self.skills = [s.strip().lower() for s in self.skills if s and s.strip()]
        self.interests = [i.strip().lower() for i in self.interests if i and i.strip()]
        self.preferred_categories = [c.strip().lower() for c in self.preferred_categories if c and c.strip()]
        self.preferred_types = [t.strip().lower() for t in self.preferred_types if t and t.strip()]
        if self.preferred_location:
            self.preferred_location = self.preferred_location.strip()
        if self.experience_level:
            self.experience_level = self.experience_level.strip().lower()
        self.delivery_mode = str(self.delivery_mode or "digest").lower().strip()
        self.digest_frequency = str(self.digest_frequency or "daily").lower().strip()
        self.timezone = str(self.timezone or "UTC").strip()
        self.quiet_hours_start = str(self.quiet_hours_start or "22:00").strip()
        self.quiet_hours_end = str(self.quiet_hours_end or "08:00").strip()

    @property
    def is_empty(self) -> bool:
        """Determines if the user has provided any personalization criteria."""
        return not (
            self.skills
            or self.interests
            or self.preferred_categories
            or self.preferred_types
            or self.prefers_remote is not None
            or self.preferred_location
            or self.experience_level
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skills": self.skills,
            "interests": self.interests,
            "preferred_categories": self.preferred_categories,
            "preferred_types": self.preferred_types,
            "prefers_remote": self.prefers_remote,
            "preferred_location": self.preferred_location,
            "experience_level": self.experience_level,
            "email_notifications_enabled": self.email_notifications_enabled,
            "in_app_notifications_enabled": self.in_app_notifications_enabled,
            "notify_new_opportunities": self.notify_new_opportunities,
            "notify_meaningful_updates": self.notify_meaningful_updates,
            "notify_reopened_opportunities": self.notify_reopened_opportunities,
            "delivery_mode": self.delivery_mode,
            "digest_frequency": self.digest_frequency,
            "quiet_hours_enabled": self.quiet_hours_enabled,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "timezone": self.timezone,
            "min_score_threshold": self.min_score_threshold,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "UserPreferencesDTO":
        if not data:
            return cls()
        return cls(
            skills=data.get("skills") or [],
            interests=data.get("interests") or [],
            preferred_categories=data.get("preferred_categories") or [],
            preferred_types=data.get("preferred_types") or [],
            prefers_remote=data.get("prefers_remote"),
            preferred_location=data.get("preferred_location"),
            experience_level=data.get("experience_level"),
            email_notifications_enabled=bool(data.get("email_notifications_enabled", True)),
            in_app_notifications_enabled=bool(data.get("in_app_notifications_enabled", True)),
            notify_new_opportunities=bool(data.get("notify_new_opportunities", True)),
            notify_meaningful_updates=bool(data.get("notify_meaningful_updates", True)),
            notify_reopened_opportunities=bool(data.get("notify_reopened_opportunities", True)),
            delivery_mode=str(data.get("delivery_mode", "digest")),
            digest_frequency=str(data.get("digest_frequency", "daily")),
            quiet_hours_enabled=bool(data.get("quiet_hours_enabled", False)),
            quiet_hours_start=str(data.get("quiet_hours_start", "22:00")),
            quiet_hours_end=str(data.get("quiet_hours_end", "08:00")),
            timezone=str(data.get("timezone", "UTC")),
            min_score_threshold=float(data.get("min_score_threshold", 0.0) or 0.0),
        )


@dataclass
class RecommendationExplanationDTO:
    """Human-readable explanation of why an opportunity was surfaced or recommended."""
    reasons: List[str] = field(default_factory=list)
    highlight_tags: List[str] = field(default_factory=list)
    match_strength: str = "moderate"  # 'strong', 'good', 'moderate'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reasons": self.reasons,
            "highlight_tags": self.highlight_tags,
            "match_strength": self.match_strength,
        }


@dataclass
class RankingResultDTO:
    """Internal container for scoring, feature contributions, and explainability."""
    opportunity_id: str
    final_score: float  # Strictly normalized in [0.0, 1.0]
    feature_scores: Dict[str, float] = field(default_factory=dict)
    eligibility: EligibilityResult = field(default_factory=EligibilityResult)
    explanation: RecommendationExplanationDTO = field(default_factory=RecommendationExplanationDTO)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "final_score": round(self.final_score, 4),
            "feature_scores": {k: round(v, 4) for k, v in self.feature_scores.items()},
            "eligibility": self.eligibility.to_dict(),
            "explanation": self.explanation.to_dict(),
        }


@dataclass
class MatchAnalysisDTO:
    """
    Explainable profile-to-opportunity match evaluation (Phase 9).
    Separates skill coverage, category alignment, and factual evidence from ranking.
    """
    opportunity_id: str = ""
    match_score: float = 0.0  # Normalized match score in [0.0, 1.0]
    skill_coverage_ratio: float = 0.0  # Ratio of opportunity skills present in profile
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)  # Skills not currently listed in profile
    matched_categories: List[str] = field(default_factory=list)
    matched_types: List[str] = field(default_factory=list)
    matched_preferences: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    match_strength: str = "moderate"  # 'strong', 'good', 'moderate'
    status: str = "UNKNOWN"  # 'MATCHED', 'PARTIAL_MATCH', 'MISSING', 'UNKNOWN'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "match_score": round(self.match_score, 4),
            "skill_coverage_ratio": round(self.skill_coverage_ratio, 4),
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "matched_categories": self.matched_categories,
            "matched_types": self.matched_types,
            "matched_preferences": self.matched_preferences,
            "reasons": self.reasons,
            "match_strength": self.match_strength,
            "status": self.status,
        }

