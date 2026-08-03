"""
Authoritative enumerations for CyberScout AI.

This module defines all canonical string enums across the pipeline according
to docs/architecture/enums.md.
"""

from enum import Enum


class StrEnum(str, Enum):
    """Base string Enum providing clean string representations."""

    def __str__(self) -> str:
        return self.value


class OpportunityCategory(StrEnum):
    """Normalized category of an opportunity."""

    INTERNSHIP = "internship"
    JOB = "job"
    COURSE = "course"
    CERTIFICATION = "certification"
    SCHOLARSHIP = "scholarship"
    HACKATHON = "hackathon"
    CTF = "ctf"
    GITHUB_REPOSITORY = "github_repository"
    SECURITY_TOOL = "security_tool"
    SECURITY_NEWS = "security_news"
    BLOG = "blog"
    TUTORIAL = "tutorial"
    RESEARCH_PAPER = "research_paper"
    OTHER = "other"


class SourceType(StrEnum):
    """Ingestion mechanism type used by a collector."""

    RSS = "rss"
    API = "api"
    HTML = "html"
    PLAYWRIGHT = "playwright"


class SourceStatus(StrEnum):
    """Operational status of a target source."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class Difficulty(StrEnum):
    """Required skill/experience level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    """Type of job or position."""

    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    UNKNOWN = "unknown"


class ProviderType(StrEnum):
    """Type of organization providing the opportunity."""

    OFFICIAL = "official"
    COMMUNITY = "community"
    EDUCATIONAL = "educational"
    NEWS = "news"
    UNKNOWN = "unknown"


class CertificateType(StrEnum):
    """Type of credential granted upon completion."""

    NONE = "none"
    COMPLETION = "completion"
    PARTICIPATION = "participation"
    DIGITAL = "digital"
    PHYSICAL = "physical"
    UNKNOWN = "unknown"


class DeliveryMode(StrEnum):
    """Delivery or venue format."""

    ONLINE = "online"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class CollectionMethod(StrEnum):
    """Ingestion protocol/method for collectors."""

    RSS = "rss"
    API = "api"
    HTML = "html"
    PLAYWRIGHT = "playwright"


class RankingReason(StrEnum):
    """Specific factors influencing ranking score."""

    FREE = "free"
    CERTIFICATE = "certificate"
    REMOTE = "remote"
    BEGINNER_FRIENDLY = "beginner_friendly"
    RECOGNIZED_PROVIDER = "recognized_provider"
    DEADLINE_SOON = "deadline_soon"
    DUPLICATE = "duplicate"
    EXPIRED = "expired"


class Status(StrEnum):
    """Lifecycle state of an Opportunity record."""

    ACTIVE = "active"
    EXPIRED = "expired"
    DUPLICATE = "duplicate"
    ARCHIVED = "archived"


# Alias for explicitly named OpportunityStatus
OpportunityStatus = Status
