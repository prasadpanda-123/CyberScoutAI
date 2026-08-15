"""
Opportunity Normalizer Processor for CyberScout AI.
"""

from typing import Optional

from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor
from src.processors.date_parser import parse_and_format_date
from src.processors.location_parser import detect_location_and_remote
from src.processors.provider_parser import normalize_provider_name


class NormalizerProcessor(BaseProcessor):
    """
    Normalizes dates, providers, locations, and remote status.
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

        # Normalize dates
        from src.processors.date_parser import extract_dates_from_text
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

        # Normalize provider
        opportunity.provider = normalize_provider_name(opportunity.provider)

        # Normalize location and remote state
        desc = opportunity.description or ""
        is_remote, is_hybrid, loc_type = detect_location_and_remote(f"{opportunity.title} {desc}")
        if is_remote:
            opportunity.remote = True

        return opportunity
