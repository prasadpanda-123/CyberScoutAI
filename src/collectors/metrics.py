"""
Collector Execution Metrics for CyberScout AI.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class CollectorMetrics:
    """
    Tracks collection performance and HTTP metrics.
    """

    requests_made: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    bytes_downloaded: int = 0
    total_latency_seconds: float = 0.0
    execution_duration_seconds: float = 0.0

    @property
    def average_latency_seconds(self) -> float:
        """Calculates average latency per successful request."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_seconds / self.successful_requests

    def record_request(self, success: bool, latency: float, num_bytes: int) -> None:
        """Records metrics for an individual HTTP request."""
        self.requests_made += 1
        self.total_latency_seconds += latency
        self.bytes_downloaded += num_bytes
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def to_dict(self) -> Dict[str, Any]:
        """Converts CollectorMetrics to dictionary."""
        res = asdict(self)
        res["average_latency_seconds"] = self.average_latency_seconds
        return res
