"""
Rule-Based Category Classifier Processor for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.models.enums import OpportunityCategory
from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor


CATEGORY_SYNONYMS: Dict[str, str] = {
    # CTF
    "ctf": OpportunityCategory.CTF.value,
    "capture the flag": OpportunityCategory.CTF.value,
    "capture-the-flag": OpportunityCategory.CTF.value,
    "jeopardy": OpportunityCategory.CTF.value,
    "jeopardy ctf": OpportunityCategory.CTF.value,

    # Internship
    "internship": OpportunityCategory.INTERNSHIP.value,
    "intern": OpportunityCategory.INTERNSHIP.value,
    "trainee": OpportunityCategory.INTERNSHIP.value,
    "fellowship": OpportunityCategory.INTERNSHIP.value,
    "student program": OpportunityCategory.INTERNSHIP.value,
    "student_program": OpportunityCategory.INTERNSHIP.value,

    # Job
    "job": OpportunityCategory.JOB.value,
    "jobs": OpportunityCategory.JOB.value,
    "career": OpportunityCategory.JOB.value,
    "employment": OpportunityCategory.JOB.value,

    # Course
    "course": OpportunityCategory.COURSE.value,
    "courses": OpportunityCategory.COURSE.value,
    "training": OpportunityCategory.COURSE.value,
    "bootcamp": OpportunityCategory.COURSE.value,
    "workshop": OpportunityCategory.COURSE.value,
    "webinar": OpportunityCategory.COURSE.value,

    # Certification
    "certification": OpportunityCategory.CERTIFICATION.value,
    "certifications": OpportunityCategory.CERTIFICATION.value,
    "cert": OpportunityCategory.CERTIFICATION.value,
    "voucher": OpportunityCategory.CERTIFICATION.value,
    "exam": OpportunityCategory.CERTIFICATION.value,

    # Scholarship
    "scholarship": OpportunityCategory.SCHOLARSHIP.value,
    "scholarships": OpportunityCategory.SCHOLARSHIP.value,
    "grant": OpportunityCategory.SCHOLARSHIP.value,
    "financial aid": OpportunityCategory.SCHOLARSHIP.value,

    # Hackathon
    "hackathon": OpportunityCategory.HACKATHON.value,
    "hackathons": OpportunityCategory.HACKATHON.value,
    "competition": OpportunityCategory.HACKATHON.value,

    # GitHub Repository
    "github_repository": OpportunityCategory.GITHUB_REPOSITORY.value,
    "github repository": OpportunityCategory.GITHUB_REPOSITORY.value,
    "github": OpportunityCategory.GITHUB_REPOSITORY.value,
    "repository": OpportunityCategory.GITHUB_REPOSITORY.value,
    "repo": OpportunityCategory.GITHUB_REPOSITORY.value,

    # Security Tool
    "security_tool": OpportunityCategory.SECURITY_TOOL.value,
    "security tool": OpportunityCategory.SECURITY_TOOL.value,
    "tool": OpportunityCategory.SECURITY_TOOL.value,

    # Security News
    "security_news": OpportunityCategory.SECURITY_NEWS.value,
    "security news": OpportunityCategory.SECURITY_NEWS.value,
    "news": OpportunityCategory.SECURITY_NEWS.value,
    "advisory": OpportunityCategory.SECURITY_NEWS.value,
    "vulnerability": OpportunityCategory.SECURITY_NEWS.value,
    "cve": OpportunityCategory.SECURITY_NEWS.value,

    # Blog
    "blog": OpportunityCategory.BLOG.value,
    "article": OpportunityCategory.BLOG.value,

    # Tutorial
    "tutorial": OpportunityCategory.TUTORIAL.value,
    "guide": OpportunityCategory.TUTORIAL.value,

    # Research Paper
    "research_paper": OpportunityCategory.RESEARCH_PAPER.value,
    "research paper": OpportunityCategory.RESEARCH_PAPER.value,
    "paper": OpportunityCategory.RESEARCH_PAPER.value,

    # Other / Fallback
    "other": OpportunityCategory.OTHER.value,
    "uncategorized": OpportunityCategory.OTHER.value,
}


VALID_CATEGORIES = frozenset(c.value for c in OpportunityCategory)


def normalize_category(raw_category: Optional[str]) -> str:
    """
    Normalizes a category string to the canonical OpportunityCategory enum value.
    Handles case variations, punctuation, and known synonyms.
    Falls back to 'other' if unknown.
    """
    if not raw_category or not isinstance(raw_category, str):
        return OpportunityCategory.OTHER.value

    cleaned = raw_category.strip().lower()
    if cleaned in CATEGORY_SYNONYMS:
        return CATEGORY_SYNONYMS[cleaned]

    # Try removing underscores / hyphens
    normalized_cleaned = cleaned.replace("_", " ").replace("-", " ")
    if normalized_cleaned in CATEGORY_SYNONYMS:
        return CATEGORY_SYNONYMS[normalized_cleaned]

    if cleaned in VALID_CATEGORIES:
        return cleaned

    return OpportunityCategory.OTHER.value


class ClassifierProcessor(BaseProcessor):
    """
    Classifies Opportunity categories using rule-based keyword matching and category normalization.
    """

    def __init__(self, enabled: bool = True, config_file: Optional[Path] = None):
        super().__init__(enabled=enabled)
        self.config_file = config_file or (CONFIG_DIR / "classification_rules.yaml")
        self.rules: Dict[str, List[str]] = {}
        self.load_configuration()

    @property
    def processor_name(self) -> str:
        return "Classifier Processor"

    def load_configuration(self) -> None:
        """Loads classification rules from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                rules_data = data.get("rules", {})
                for cat, cinfo in rules_data.items():
                    if isinstance(cinfo, dict) and "keywords" in cinfo:
                        self.rules[cat] = cinfo["keywords"]
            except Exception:
                pass

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Classifies and normalizes category for Opportunity.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Opportunity instance with updated canonical category.
        """
        if not self.enabled:
            return opportunity

        # Normalize incoming category if already set
        if opportunity.category and opportunity.category != OpportunityCategory.OTHER.value:
            opportunity.category = normalize_category(opportunity.category)
            if opportunity.category != OpportunityCategory.OTHER.value:
                return opportunity

        text_lower = f"{opportunity.title} {opportunity.description or ''}".lower()

        for cat, keywords in self.rules.items():
            if any(kw in text_lower for kw in keywords):
                canonical_cat = normalize_category(cat)
                if canonical_cat != OpportunityCategory.OTHER.value:
                    opportunity.category = canonical_cat
                    return opportunity

        opportunity.category = normalize_category(opportunity.category)
        return opportunity

