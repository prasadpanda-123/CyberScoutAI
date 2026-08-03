"""
Collector Context for CyberScout AI Collection Framework.
"""

from dataclasses import dataclass
from typing import Optional

from src.collectors.cache import CollectorCache
from src.collectors.http_client import HTTPClient
from src.collectors.rate_limiter import RateLimiter
from src.collectors.robots import RobotsChecker


@dataclass
class CollectorContext:
    """
    Runtime execution context passed to collectors.
    """

    http_client: HTTPClient
    cache: CollectorCache
    rate_limiter: RateLimiter
    robots_checker: RobotsChecker

    @classmethod
    def create_default(cls) -> "CollectorContext":
        """Instantiates default shared context services."""
        cache = CollectorCache()
        rate_limiter = RateLimiter()
        robots_checker = RobotsChecker()
        http_client = HTTPClient(cache=cache, rate_limiter=rate_limiter)
        return cls(
            http_client=http_client,
            cache=cache,
            rate_limiter=rate_limiter,
            robots_checker=robots_checker,
        )
