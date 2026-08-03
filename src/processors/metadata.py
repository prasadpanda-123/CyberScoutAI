"""
Metadata Extractor Processor for CyberScout AI.
"""

from typing import Optional

from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor
from src.processors.company_parser import extract_company_name


class MetadataExtractorProcessor(BaseProcessor):
    """
    Extracts structured metadata (company name, certificate, paid state, duration).
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)

    @property
    def processor_name(self) -> str:
        return "Metadata Extractor Processor"

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Extracts metadata into Opportunity fields and raw_data.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Opportunity instance with populated metadata.
        """
        if not self.enabled:
            return opportunity

        # Extract company name
        if not opportunity.company:
            opportunity.company = extract_company_name(opportunity.title, opportunity.provider)

        text_lower = f"{opportunity.title} {opportunity.description or ''}".lower()

        # Certificate detection
        if any(k in text_lower for k in ["certificate", "certification", "accredited"]):
            opportunity.certificate = True

        # Paid / Free detection
        if opportunity.paid is None:
            if any(k in text_lower for k in ["free", "no cost", "complimentary"]):
                opportunity.paid = False

        return opportunity
