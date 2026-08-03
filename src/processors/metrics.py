"""
Processing Metrics for CyberScout AI.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class ProcessingMetrics:
    """
    Tracks pipeline processing throughput, execution duration, rejection, and duplicate statistics.
    """

    processed_count: int = 0
    passed_count: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0
    total_duration_seconds: float = 0.0

    def record_processed(self, passed: bool = True, is_duplicate: bool = False) -> None:
        """Records metrics for an individual processed Opportunity."""
        self.processed_count += 1
        if is_duplicate:
            self.duplicate_count += 1
        if passed:
            self.passed_count += 1
        else:
            self.rejected_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Converts ProcessingMetrics instance to dictionary."""
        return asdict(self)
