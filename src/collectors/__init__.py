"""
Universal Collection Framework and Core Collectors Package for CyberScout AI.
"""

from src.collectors.base import BaseCollector
from src.collectors.cache import CollectorCache
from src.collectors.context import CollectorContext
from src.collectors.ctftime_collector import CtftimeCollector
from src.collectors.exceptions import (
    CollectorError,
    HTTPClientError,
    ParsingError,
    RateLimitError,
    RobotsForbiddenError,
)
from src.collectors.factory import CollectorFactory
from src.collectors.github_collector import GithubSearchCollector
from src.collectors.http_client import HTTPClient
from src.collectors.manager import CollectorManager
from src.collectors.metrics import CollectorMetrics
from src.collectors.parser_utils import (
    normalize_url,
    parse_html_content,
    parse_json_content,
    parse_rss_xml_content,
)
from src.collectors.rate_limiter import RateLimiter
from src.collectors.registry import CollectorRegistry
from src.collectors.result import CollectorResult
from src.collectors.retry import CollectorRetry
from src.collectors.robots import RobotsChecker
from src.collectors.rss_collector import GenericRSSCollector
from src.collectors.youtube_collector import YouTubeRSSCollector

__all__ = [
    "BaseCollector",
    "GenericRSSCollector",
    "GithubSearchCollector",
    "YouTubeRSSCollector",
    "CtftimeCollector",
    "CollectorResult",
    "CollectorMetrics",
    "CollectorContext",
    "HTTPClient",
    "CollectorCache",
    "RateLimiter",
    "CollectorRetry",
    "RobotsChecker",
    "CollectorRegistry",
    "CollectorFactory",
    "CollectorManager",
    "CollectorError",
    "HTTPClientError",
    "RateLimitError",
    "RobotsForbiddenError",
    "ParsingError",
    "parse_json_content",
    "parse_html_content",
    "parse_rss_xml_content",
    "normalize_url",
]
