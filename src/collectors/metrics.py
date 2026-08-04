"""
Collector Execution Metrics for CyberScout AI.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class CollectorMetrics:
    """
    Tracks collection performance, provider health statistics, and HTTP metrics.
    """

    requests_made: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    providers_attempted: int = 0
    providers_succeeded: int = 0
    providers_failed: int = 0
    timeouts_count: int = 0
    rss_failures: int = 0
    html_failures: int = 0
    api_failures: int = 0
    total_items_collected: int = 0
    bytes_downloaded: int = 0
    total_latency_seconds: float = 0.0
    execution_duration_seconds: float = 0.0

    @property
    def average_latency_seconds(self) -> float:
        """Calculates average latency per successful request."""
        if self.successful_requests == 0:
            return 0.0
        return round(self.total_latency_seconds / self.successful_requests, 3)

    def record_request(self, success: bool, latency: float, num_bytes: int) -> None:
        """Records metrics for an individual HTTP request."""
        self.requests_made += 1
        self.total_latency_seconds += latency
        self.bytes_downloaded += num_bytes
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def record_provider_result(
        self,
        source_id: str,
        method: str,
        success: bool,
        item_count: int = 0,
        is_timeout: bool = False,
    ) -> None:
        """Records provider task completion result."""
        self.providers_attempted += 1
        self.total_items_collected += item_count

        if success:
            self.providers_succeeded += 1
        else:
            self.providers_failed += 1
            if is_timeout:
                self.timeouts_count += 1
            if method == "rss":
                self.rss_failures += 1
            elif method == "html":
                self.html_failures += 1
            elif method == "api":
                self.api_failures += 1

    def to_dict(self) -> Dict[str, Any]:
        """Converts CollectorMetrics to dictionary."""
        res = asdict(self)
        res["average_latency_seconds"] = self.average_latency_seconds
        return res
