"""
Opportunity Deduplicator Processor for CyberScout AI.
"""

from typing import Optional, Set

from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor


class DeduplicatorProcessor(BaseProcessor):
    """
    In-memory duplicate detector tracking seen URL hashes and title signatures.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.seen_hashes: Set[str] = set()

    @property
    def processor_name(self) -> str:
        return "Deduplicator Processor"

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Detects duplicates.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Opportunity instance, or None if duplicate detected.
        """
        if not self.enabled:
            return opportunity

        url_hash = opportunity.generate_url_hash()
        if url_hash in self.seen_hashes:
            # Duplicate detected
            return None

        self.seen_hashes.add(url_hash)
        return opportunity
