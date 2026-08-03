"""
Opportunity Validator Processor for CyberScout AI.
"""

from typing import Optional

from src.models.enums import OpportunityCategory
from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor
from src.processors.exceptions import ValidationError
from src.utils.validation_utils import is_valid_url


class ValidatorProcessor(BaseProcessor):
    """
    Validates structural requirements of an Opportunity instance.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)

    @property
    def processor_name(self) -> str:
        return "Validator Processor"

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Validates Opportunity fields.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Validated Opportunity instance, or raises ValidationError.
        """
        if not self.enabled:
            return opportunity

        # 1. Title validation
        if not opportunity.title or not opportunity.title.strip():
            raise ValidationError("Opportunity title is missing or empty.")

        # 2. URL validation
        if not opportunity.url or not is_valid_url(opportunity.url):
            raise ValidationError(f"Invalid URL format: '{opportunity.url}'.")

        # 3. Category validation
        valid_categories = [c.value for c in OpportunityCategory]
        if opportunity.category not in valid_categories:
            opportunity.category = OpportunityCategory.OTHER.value

        return opportunity
