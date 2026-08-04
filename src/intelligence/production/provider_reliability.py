"""
Feature 1: Source Reliability Engine for CyberScout AI (Phase 12).
"""

from typing import Any, Dict, List, Optional
from src.intelligence.production.statistics import ProviderStats


class ProviderReliabilityEngine:
    """
    Evaluates provider credibility ratings and tracks execution telemetry.
    """

    DEFAULT_SCORES: Dict[str, float] = {
        "cisa_alerts": 100.0,
        "us_cert": 100.0,
        "github_api": 95.0,
        "ctftime_api": 95.0,
        "owasp_feed": 95.0,
        "portswigger_blog": 95.0,
        "hackthebox_news": 90.0,
        "tryhackme_blog": 90.0,
        "generic_rss": 60.0,
        "html_scraper": 50.0,
    }

    def __init__(self, custom_defaults: Optional[Dict[str, float]] = None):
        self.defaults = custom_defaults or self.DEFAULT_SCORES
        self.stats: Dict[str, ProviderStats] = {}

    def get_or_create_stats(self, provider_name: str) -> ProviderStats:
        if provider_name not in self.stats:
            default_score = self.defaults.get(provider_name, 70.0)
            self.stats[provider_name] = ProviderStats(
                provider_name=provider_name,
                reliability_score=default_score
            )
        return self.stats[provider_name]

    def record_request_outcome(
        self,
        provider_name: str,
        success: bool,
        response_time: float = 0.5,
        is_dns: bool = False,
        is_timeout: bool = False,
    ) -> ProviderStats:
        pstats = self.get_or_create_stats(provider_name)
        if success:
            pstats.record_success(response_time)
        else:
            pstats.record_failure(is_dns=is_dns, is_timeout=is_timeout)

        # Recalculate score
        pstats.reliability_score = self.calculate_reliability_score(pstats)
        return pstats

    def calculate_reliability_score(self, stats: ProviderStats) -> float:
        """
        Calculates composite provider reliability score (0 - 100).
        """
        base = self.defaults.get(stats.provider_name, 70.0)
        if stats.total_requests == 0:
            return base

        # Penalty factor based on failure rate and consecutive failures
        fail_penalty = (stats.failure_rate * 0.4)
        consecutive_penalty = min(30.0, stats.consecutive_failures * 10.0)
        dns_penalty = stats.dns_failures * 5.0
        timeout_penalty = stats.timeouts * 3.0

        # Speed bonus/penalty
        speed_adj = 0.0
        if stats.average_response_time > 3.0:
            speed_adj = -10.0
        elif stats.average_response_time < 0.5:
            speed_adj = 5.0

        raw_score = base - fail_penalty - consecutive_penalty - dns_penalty - timeout_penalty + speed_adj
        return max(0.0, min(100.0, round(raw_score, 1)))

    def get_provider_rankings(self) -> List[Dict[str, Any]]:
        """Returns sorted list of provider statistics by reliability score."""
        sorted_stats = sorted(self.stats.values(), key=lambda s: s.reliability_score, reverse=True)
        return [s.to_dict() for s in sorted_stats]
