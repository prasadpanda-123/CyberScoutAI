"""
Sequential Processing Pipeline for CyberScout AI.
"""

import time
from typing import List, Optional

from src.core.logging import get_logger
from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor
from src.processors.classifier import ClassifierProcessor
from src.processors.cleaner import CleanerProcessor
from src.processors.deduplicator import DeduplicatorProcessor
from src.processors.exceptions import ProcessingError
from src.processors.keyword_extractor import KeywordExtractorProcessor
from src.processors.metadata import MetadataExtractorProcessor
from src.processors.metrics import ProcessingMetrics
from src.processors.normalizer import NormalizerProcessor
from src.processors.quality_checker import QualityCheckerProcessor
from src.processors.validator import ValidatorProcessor

logger = get_logger(__name__)


class ProcessingPipeline:
    """
    Configurable sequential execution pipeline for processors.
    """

    def __init__(self, processors: Optional[List[BaseProcessor]] = None):
        self.processors = processors or self._create_default_processors()
        self.metrics = ProcessingMetrics()

    def _create_default_processors(self) -> List[BaseProcessor]:
        """Instantiates standard default pipeline processors in strict order."""
        return [
            ValidatorProcessor(),
            CleanerProcessor(),
            NormalizerProcessor(),
            MetadataExtractorProcessor(),
            KeywordExtractorProcessor(),
            ClassifierProcessor(),
            DeduplicatorProcessor(),
            QualityCheckerProcessor(),
        ]

    def process_item(self, raw_item: Opportunity) -> Optional[Opportunity]:
        """
        Executes pipeline processors sequentially on a single Opportunity.

        Args:
            raw_item: Input Opportunity instance.

        Returns:
            Fully processed Opportunity instance, or None if rejected/duplicate.
        """
        current: Optional[Opportunity] = raw_item

        for processor in self.processors:
            if not current:
                break
            if not processor.enabled:
                continue

            try:
                current = processor.process(current)
            except Exception as e:
                logger.warning(f"Processor '{processor.processor_name}' rejected item '{raw_item.title}': {e}")
                self.metrics.record_processed(passed=False)
                return None

        if current:
            self.metrics.record_processed(passed=True)
        else:
            self.metrics.record_processed(passed=False, is_duplicate=True)

        return current

    def process_batch(self, items: List[Opportunity]) -> List[Opportunity]:
        """
        Executes pipeline processing over a batch of Opportunity instances.

        Args:
            items: List of raw Opportunity instances.

        Returns:
            List of clean, normalized, non-duplicate Opportunity instances.
        """
        start_time = time.time()
        processed_batch: List[Opportunity] = []

        for item in items:
            res = self.process_item(item)
            if res:
                processed_batch.append(res)

        self.metrics.total_duration_seconds = time.time() - start_time
        logger.info(
            f"ProcessingPipeline processed {len(items)} items -> {len(processed_batch)} valid opportunities "
            f"in {self.metrics.total_duration_seconds:.2f}s."
        )
        return processed_batch
