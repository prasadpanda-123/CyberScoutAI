"""
Opportunity Normalizer Processor for CyberScout AI.
"""

from typing import Optional

from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor
from src.processors.classifier import normalize_category
from src.processors.date_parser import extract_dates_from_text, parse_and_format_date, validate_dates
from src.processors.location_parser import detect_location_and_remote
from src.processors.provider_parser import normalize_provider_name
from src.utils.url_utils import normalize_url


class NormalizerProcessor(BaseProcessor):
    """
    Normalizes URLs, dates, categories, providers, locations, and remote status.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)

    @property
    def processor_name(self) -> str:
        return "Normalizer Processor"

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Normalizes Opportunity field formats.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Normalized Opportunity instance.
        """
        if not self.enabled:
            return opportunity

        # 1. Normalize and Canonicalize URL
        if opportunity.url:
            canonical_url = normalize_url(opportunity.url)
            if canonical_url:
                opportunity.url = canonical_url

        # 2. Normalize dates
        if opportunity.published_date:
            opportunity.published_date = parse_and_format_date(opportunity.published_date)
        if opportunity.deadline:
            opportunity.deadline = parse_and_format_date(opportunity.deadline)

        # Contextual date extraction from text if fields are missing
        if not opportunity.published_date or not opportunity.deadline:
            full_text = f"{opportunity.title}\n{opportunity.description or ''}"
            extracted = extract_dates_from_text(full_text)
            if not opportunity.published_date and extracted.get("published_date"):
                opportunity.published_date = extracted["published_date"]
            if not opportunity.deadline and extracted.get("deadline"):
                opportunity.deadline = extracted["deadline"]

        # 3. Validate date consistency (release_date <= deadline)
        is_valid_dates, date_issue = validate_dates(opportunity.published_date, opportunity.deadline)
        if not is_valid_dates and date_issue:
            flags = opportunity.quality_flags.split(",") if opportunity.quality_flags else []
            flags.append("invalid_date_order")
            opportunity.quality_flags = ",".join(f.strip() for f in flags if f.strip())

        # 4. Normalize category
        if opportunity.category:
            opportunity.category = normalize_category(opportunity.category)

        # 5. Normalize provider
        opportunity.provider = normalize_provider_name(opportunity.provider)

        # 6. Normalize location and remote state
        desc = opportunity.description or ""
        is_remote, is_hybrid, loc_type = detect_location_and_remote(f"{opportunity.title} {desc}")
        if is_remote:
            opportunity.remote = True

        return opportunity

