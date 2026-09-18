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


class SourceFamily(StrEnum):
    """Authoritative taxonomy of opportunity source families."""

    INDIAN_INTERNSHIP = "indian_internship"
    GLOBAL_INTERNSHIP = "global_internship"
    JOB = "job"
    HACKATHON = "hackathon"
    COMPETITION = "competition"
    CTF = "ctf"
    CYBERSECURITY = "cybersecurity"
    BUG_BOUNTY = "bug_bounty"
    SECURITY_RESEARCH = "security_research"
    COURSE = "course"
    CERTIFICATION = "certification"
    OPEN_SOURCE = "open_source"
    RESEARCH = "research"
    SCHOLARSHIP = "scholarship"
    FELLOWSHIP = "fellowship"
    WORKSHOP = "workshop"
    WEBINAR = "webinar"
    CONFERENCE = "conference"
    CHALLENGE = "challenge"
    APPRENTICESHIP = "apprenticeship"


class OpportunityType(StrEnum):
    """Canonical taxonomy of opportunity types."""

    INTERNSHIP = "internship"
    JOB = "job"
    COURSE = "course"
    CERTIFICATION = "certification"
    CTF = "ctf"
    HACKATHON = "hackathon"
    COMPETITION = "competition"
    SCHOLARSHIP = "scholarship"
    FELLOWSHIP = "fellowship"
    OPEN_SOURCE = "open_source"
    RESEARCH = "research"
    BUG_BOUNTY = "bug_bounty"
    SECURITY_RESEARCH = "security_research"
    WORKSHOP = "workshop"
    WEBINAR = "webinar"
    CONFERENCE = "conference"
    CHALLENGE = "challenge"
    APPRENTICESHIP = "apprenticeship"


class PricingType(StrEnum):
    """Payment and pricing classification for individual opportunities."""

    FREE = "free"
    PAID = "paid"
    FREEMIUM = "freemium"
    UNKNOWN = "unknown"


class StipendType(StrEnum):
    """Stipend model for internships, fellowships, and research."""

    NONE = "none"
    UNKNOWN = "unknown"
    PAID = "paid"


class CertificateCost(StrEnum):
    """Credential and certificate pricing model."""

    FREE = "free"
    PAID = "paid"
    UNKNOWN = "unknown"


class CertificateAvailable(StrEnum):
    """Whether completion credentials or certificates are available."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class TrustTier(StrEnum):
    """Authoritative source reliability and trust tier."""

    TIER_1 = "tier_1"  # Official government, educational institution, vendor, foundation
    TIER_2 = "tier_2"  # Established opportunity platform with reliable structured listings
    TIER_3 = "tier_3"  # Aggregator/community source requiring additional verification
    TIER_4 = "tier_4"  # Unverified/manual-review source


class HealthStatus(StrEnum):
    """Runtime health status of an opportunity source."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    DISABLED = "disabled"
    MANUAL_REVIEW = "manual_review"
    UNSUPPORTED = "unsupported"


class CollectorFailureClass(StrEnum):
    """Failure classifications for collector telemetry and isolation."""

    SOURCE_FAILURE = "source_failure"
    PIPELINE_FAILURE = "pipeline_failure"
    DATABASE_FAILURE = "database_failure"
    CONFIGURATION_FAILURE = "configuration_failure"
    VALIDATION_FAILURE = "validation_failure"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_FAILURE = "authentication_failure"
    PARSER_FAILURE = "parser_failure"
    TIMEOUT = "timeout"

    @classmethod
    def classify(cls, exc: Exception) -> str:
        """Classifies an arbitrary exception into a standard CollectorFailureClass string value."""
        if exc is None:
            return cls.SOURCE_FAILURE.value

        exc_name = type(exc).__name__.lower()
        err_msg = str(exc).lower()

        if "timeout" in exc_name or "timeout" in err_msg or "timed out" in err_msg:
            return cls.TIMEOUT.value
        elif "ratelimit" in exc_name or "429" in err_msg or "too many requests" in err_msg:
            return cls.RATE_LIMIT.value
        elif "parser" in exc_name or "parse" in exc_name or "bs4" in exc_name or "syntax" in err_msg:
            return cls.PARSER_FAILURE.value
        elif "auth" in exc_name or "permission" in exc_name or "401" in err_msg or "403" in err_msg or "unauthorized" in err_msg:
            return cls.AUTHENTICATION_FAILURE.value
        elif "database" in exc_name or "integrity" in exc_name or "repository" in exc_name or "sql" in err_msg:
            return cls.DATABASE_FAILURE.value
        elif "config" in exc_name:
            return cls.CONFIGURATION_FAILURE.value
        elif "validation" in exc_name:
            return cls.VALIDATION_FAILURE.value
        elif "pipeline" in exc_name:
            return cls.PIPELINE_FAILURE.value
        return cls.SOURCE_FAILURE.value


class TermsReviewStatus(StrEnum):
    """Terms of service and legal review status for crawling/harvesting."""

    APPROVED = "approved"
    RESTRICTED = "restricted"
    PENDING_REVIEW = "pending_review"
    PROHIBITED = "prohibited"


class RobotsPolicy(StrEnum):
    """robots.txt crawling compliance policy."""

    RESPECT = "respect"
    CUSTOM = "custom"
    NOT_APPLICABLE = "not_applicable"


class AccessMethod(StrEnum):
    """Acquisition mechanism used for harvesting from a source."""

    API = "api"
    RSS = "rss"
    OFFICIAL_FEED = "official_feed"
    STRUCTURED_ENDPOINT = "structured_endpoint"
    HTML_EXTRACTION = "html_extraction"
    MANUAL_CURATED = "manual_curated"
    UNSUPPORTED = "unsupported"


class ChangeClassification(StrEnum):
    """Deterministic change classification of an opportunity candidate during harvesting."""

    NEW = "NEW"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    REOPENED = "REOPENED"
    CLOSED = "CLOSED"
    REMOVED = "REMOVED"
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"


class LifecycleStatus(StrEnum):
    """Authoritative lifecycle state of an opportunity."""

    ACTIVE = "active"
    CLOSING_SOON = "closing_soon"
    EXPIRED = "expired"
    CLOSED = "closed"
    REOPENED = "reopened"
    REMOVED = "removed"


class QualityStatus(StrEnum):
    """Authoritative data quality classification of an opportunity."""

    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    STALE = "stale"
    SEVERELY_STALE = "severely_stale"
    QUARANTINED = "quarantined"


class FieldCompleteness(StrEnum):
    """Importance classification for field completeness auditing."""

    REQUIRED = "required"
    IMPORTANT = "important"
    OPTIONAL = "optional"


class FreshnessStatus(StrEnum):
    """Temporal freshness state of an opportunity or source."""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    SEVERELY_STALE = "severely_stale"


class NotificationEventType(StrEnum):
    """Event types eligible for user alerting."""

    NEW = "new"
    UPDATED = "updated"
    REOPENED = "reopened"


class NotificationStatus(StrEnum):
    """Outbox state machine status."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationDeliveryMode(StrEnum):
    """User delivery timing mode."""

    IMMEDIATE = "immediate"
    DIGEST = "digest"


class NotificationChannel(StrEnum):
    """Notification transmission medium."""

    EMAIL = "email"
    IN_APP = "in_app"
