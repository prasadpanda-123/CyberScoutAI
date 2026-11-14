"""
CyberScout AI Discovery, Extraction & Classification Package.

Phase B, Phase C & Phase D Architecture:
- Global AI-Powered Cybersecurity Opportunity Discovery Engine (Tavily Search API)
- Deep Content Extraction Subsystem (Firecrawl Scrape API)
- Multi-Provider AI Opportunity Classification Engine (Groq Primary + Google Gemini Fallback)
- Strict URL Security, SSRF defense, and candidate staging in DiscoveredCandidates
"""

from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.classification_models import (
    AIProviderMetrics,
    ClassificationBudget,
    ClassificationCategory,
    ClassificationResult,
    ClassificationRunSummary,
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
from src.discovery.classification_repository import ClassificationRepository
from src.discovery.classification_schema import (
    AI_CLASSIFICATION_PROMPT_VERSION,
    CLASSIFICATION_JSON_SCHEMA,
    CLASSIFICATION_SYSTEM_PROMPT,
    build_classification_user_prompt,
)
from src.discovery.classification_service import AIClassificationService
from src.discovery.classification_validator import ClassificationValidator
from src.discovery.client_firecrawl import (
    FirecrawlAPIError,
    FirecrawlAuthError,
    FirecrawlBudgetExceededError,
    FirecrawlClient,
    FirecrawlClientMetrics,
    FirecrawlError,
    FirecrawlRateLimitError,
    FirecrawlSecurityError,
    FirecrawlTimeoutError,
    sanitize_firecrawl_secret,
)
from src.discovery.client_gemini import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiClient,
    GeminiError,
    GeminiQuotaError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    sanitize_gemini_secret,
)
from src.discovery.client_groq import (
    GroqAPIError,
    GroqAuthError,
    GroqClient,
    GroqError,
    GroqQuotaError,
    GroqRateLimitError,
    GroqTimeoutError,
    sanitize_groq_secret,
)
from src.discovery.client_tavily import (
    TavilyAPIError,
    TavilyAuthError,
    TavilyBudgetExceededError,
    TavilyClient,
    TavilyHealthMetrics,
    TavilyRateLimitError,
    TavilyTimeoutError,
    sanitize_secret,
)
from src.discovery.discovery_models import (
    CandidateProcessingStatus,
    DiscoveredCandidate,
    DiscoveryBudget,
    DiscoveryRunSummary,
    ExtractedContentData,
    ExtractionBudget,
    ExtractionRunSummary,
    ExtractionStatus,
    GeographicRegion,
    OpportunityCategory,
    PricingVerificationStatus,
    SearchQuerySpec,
)
from src.discovery.discovery_service import GlobalDiscoveryService
from src.discovery.extraction_service import FirecrawlExtractionService
from src.discovery.free_only_models import (
    FinancialDimension,
    FreeOnlyDecision,
    FreeOnlyEvaluation,
    FreeOnlyRunSummary,
    VerifiedPricingEvidence,
)
from src.discovery.free_only_repository import FreeOnlyRepository
from src.discovery.free_only_rules import FREE_ONLY_RULE_VERSION, FreeOnlyRuleEngine
from src.discovery.daily_excel_report import DailyExcelReportGenerator, escape_formula_injection
from src.discovery.notification_delivery_service import NotificationDeliveryService
from src.discovery.opportunity_ranker import OpportunityRanker
from src.discovery.production_deduplication import ProductionDeduplicator
from src.discovery.promotion_models import (
    CandidatePromotionEvaluation,
    DailyReportMetadata,
    EmailDeliveryRecord,
    OpportunityFieldValidationResult,
    PromotionDecision,
    PromotionRunSummary,
    PromotionStatus,
)
from src.discovery.promotion_repository import PromotionRepository
from src.discovery.promotion_service import ProductionPromotionService
from src.discovery.pricing_evidence_validator import PricingEvidenceValidator
from src.discovery.platform_registry import PlatformDefinition, PlatformRegistry
from src.discovery.query_planner import DiscoveryQueryPlanner
from src.discovery.region_registry import RegionRegistry
from src.discovery.url_validator import URLValidationResult, URLValidator

__all__ = [
    # Discovery (Tavily)
    "TavilyClient",
    "TavilyHealthMetrics",
    "GlobalDiscoveryService",
    "DiscoveryQueryPlanner",
    "DiscoveredCandidateRepository",
    "URLValidator",
    "URLValidationResult",
    "RegionRegistry",
    "PlatformRegistry",
    "PlatformDefinition",
    "sanitize_secret",
    # Extraction (Firecrawl - Phase C)
    "FirecrawlClient",
    "FirecrawlClientMetrics",
    "FirecrawlExtractionService",
    "sanitize_firecrawl_secret",
    "FirecrawlError",
    "FirecrawlAuthError",
    "FirecrawlRateLimitError",
    "FirecrawlBudgetExceededError",
    "FirecrawlTimeoutError",
    "FirecrawlSecurityError",
    "FirecrawlAPIError",
    # Classification (Phase D - Groq & Gemini)
    "GroqClient",
    "GroqError",
    "GroqAuthError",
    "GroqRateLimitError",
    "GroqQuotaError",
    "GroqTimeoutError",
    "GroqAPIError",
    "sanitize_groq_secret",
    "GeminiClient",
    "GeminiError",
    "GeminiAuthError",
    "GeminiRateLimitError",
    "GeminiQuotaError",
    "GeminiTimeoutError",
    "GeminiAPIError",
    "sanitize_gemini_secret",
    "AIClassificationService",
    "ClassificationValidator",
    "ClassificationRepository",
    "ClassificationCategory",
    "ExperienceLevel",
    "WorkMode",
    "ParticipationCostStatus",
    "FeeStatus",
    "CompensationStatus",
    "EligibilityData",
    "LocationData",
    "DatesData",
    "FinancialClassification",
    "EvidenceItem",
    "ClassificationResult",
    "ClassificationBudget",
    "ClassificationRunSummary",
    "AIProviderMetrics",
    "AI_CLASSIFICATION_PROMPT_VERSION",
    "CLASSIFICATION_JSON_SCHEMA",
    "CLASSIFICATION_SYSTEM_PROMPT",
    "build_classification_user_prompt",
    # Models & Enums
    "DiscoveredCandidate",
    "SearchQuerySpec",
    "DiscoveryBudget",
    "DiscoveryRunSummary",
    "ExtractionBudget",
    "ExtractedContentData",
    "ExtractionRunSummary",
    "OpportunityCategory",
    "GeographicRegion",
    "CandidateProcessingStatus",
    "ExtractionStatus",
    "PricingVerificationStatus",
    # Exceptions
    "TavilyAPIError",
    "TavilyAuthError",
    "TavilyRateLimitError",
    "TavilyTimeoutError",
    "TavilyBudgetExceededError",
    # Free-Only Verification (Phase E)
    "FreeOnlyDecision",
    "FinancialDimension",
    "VerifiedPricingEvidence",
    "FreeOnlyEvaluation",
    "FreeOnlyRunSummary",
    "PricingEvidenceValidator",
    "FreeOnlyRuleEngine",
    "FREE_ONLY_RULE_VERSION",
    "FreeOnlyRepository",
    "FreeOnlyVerifier",
    # Production Promotion & Notification (Phase F)
    "PromotionDecision",
    "PromotionStatus",
    "OpportunityFieldValidationResult",
    "CandidatePromotionEvaluation",
    "PromotionRunSummary",
    "DailyReportMetadata",
    "EmailDeliveryRecord",
    "ProductionDeduplicator",
    "OpportunityRanker",
    "DailyExcelReportGenerator",
    "escape_formula_injection",
    "PromotionRepository",
    "ProductionPromotionService",
    "NotificationDeliveryService",
]
