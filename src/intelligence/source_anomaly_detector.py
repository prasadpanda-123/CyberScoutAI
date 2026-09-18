"""
Authoritative Parser Regression & Anomaly Detector for CyberScout AI (Phase 6).

Detects sudden drops in harvested item count (e.g. >= 90% drop from baseline) or high
validation failure rates (e.g. >= 90% malformed items) to isolate bad batches and
prevent destructive overwriting of good canonical data.
"""

from typing import List, Optional

from src.core.logging import get_logger
from src.models.data_quality_models import SourceAnomalyReportDTO, ValidationResultDTO
from src.models.enums import QualityStatus
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


class SourceAnomalyDetector:
    """
    Deterministic detector identifying parser regressions and collection yield collapses.
    """

    def __init__(
        self,
        min_historical_baseline: int = 10,
        severe_drop_threshold_pct: float = 90.0,
        malformed_rate_threshold_pct: float = 90.0,
    ):
        self.min_historical_baseline = min_historical_baseline
        self.severe_drop_threshold_pct = severe_drop_threshold_pct
        self.malformed_rate_threshold_pct = malformed_rate_threshold_pct

    def check_batch_anomaly(
        self,
        source_id: str,
        current_items: List[Opportunity],
        malformed_count: int = 0,
        historical_average_count: float = 10.0,
        validation_results: Optional[List[ValidationResultDTO]] = None,
    ) -> SourceAnomalyReportDTO:
        """Helper to inspect batch anomaly with explicit counts."""
        val_results = validation_results
        if val_results is None and malformed_count > 0:
            val_results = [
                ValidationResultDTO(quality_status=QualityStatus.QUARANTINED if i < malformed_count else QualityStatus.PASSED)
                for i in range(len(current_items))
            ]
        return self.check_anomaly(
            source_id=source_id,
            current_items=current_items,
            historical_average=historical_average_count,
            validation_results=val_results,
        )

    def check_anomaly(
        self,
        source_id: str,
        current_items: List[Opportunity],
        historical_average: float,
        validation_results: Optional[List[ValidationResultDTO]] = None,
    ) -> SourceAnomalyReportDTO:
        """
        Inspects incoming batch yield against historical baseline.

        Args:
            source_id: Unique identifier of the source.
            current_items: List of opportunities harvested in the current run.
            historical_average: Average item count from past successful runs.
            validation_results: Optional list of validation results for this batch.

        Returns:
            SourceAnomalyReportDTO indicating whether an anomaly was detected.
        """
        current_count = len(current_items)
        drop_pct = 0.0

        if historical_average >= self.min_historical_baseline:
            if current_count < historical_average:
                drop_pct = ((historical_average - current_count) / historical_average) * 100.0

        # Compute validation failure rate
        val_failure_rate = 0.0
        if validation_results and len(validation_results) > 0:
            quarantined_count = sum(
                1 for r in validation_results if r.quality_status == QualityStatus.QUARANTINED
            )
            val_failure_rate = (quarantined_count / len(validation_results)) * 100.0

        anomaly_detected = False
        reasons = []

        # Check for extreme yield drop
        if historical_average >= self.min_historical_baseline and drop_pct >= self.severe_drop_threshold_pct:
            anomaly_detected = True
            reasons.append(
                f"Severe item drop of {drop_pct:.1f}% (baseline {historical_average:.1f} -> current {current_count})"
            )

        # Check for extreme malformed item rate
        if len(current_items) >= 5 and val_failure_rate >= self.malformed_rate_threshold_pct:
            anomaly_detected = True
            reasons.append(
                f"Severe validation failure rate of {val_failure_rate:.1f}% ({quarantined_count}/{len(validation_results)} quarantined)"
            )

        message = "Normal harvest yield" if not anomaly_detected else " | ".join(reasons)
        if anomaly_detected:
            logger.warning(f"[AnomalyDetector] Anomaly detected for source '{source_id}': {message}")

        return SourceAnomalyReportDTO(
            source_id=source_id,
            anomaly_detected=anomaly_detected,
            historical_average=historical_average,
            current_count=current_count,
            drop_percentage=drop_pct,
            validation_failure_rate=val_failure_rate,
            quarantine_applied=anomaly_detected,
            message=message,
        )
