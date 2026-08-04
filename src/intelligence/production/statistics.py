"""
Provider & System Statistics Data Aggregator for Production Data Intelligence.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ProviderStats:
    """Statistics container for a single opportunity provider."""
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    dns_failures: int = 0
    timeouts: int = 0
    total_response_time: float = 0.0
    consecutive_failures: int = 0
    reliability_score: float = 100.0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 100.0
        return round((self.successful_requests / self.total_requests) * 100.0, 1)

    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round((self.failed_requests / self.total_requests) * 100.0, 1)

    @property
    def average_response_time(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.total_response_time / self.total_requests, 3)

    @property
    def star_rating(self) -> str:
        """Returns 1-5 star rating string representation."""
        if self.reliability_score >= 90:
            return "★★★★★"
        elif self.reliability_score >= 75:
            return "★★★★☆"
        elif self.reliability_score >= 60:
            return "★★★☆☆"
        elif self.reliability_score >= 40:
            return "★★☆☆☆"
        else:
            return "★☆☆☆☆"

    def record_success(self, response_time: float = 0.5) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_response_time += response_time
        self.consecutive_failures = 0
        self.last_success = datetime.now(timezone.utc).isoformat()

    def record_failure(self, is_dns: bool = False, is_timeout: bool = False) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        if is_dns:
            self.dns_failures += 1
        if is_timeout:
            self.timeouts += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "dns_failures": self.dns_failures,
            "timeouts": self.timeouts,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "average_response_time": self.average_response_time,
            "consecutive_failures": self.consecutive_failures,
            "reliability_score": self.reliability_score,
            "star_rating": self.star_rating,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
        }
