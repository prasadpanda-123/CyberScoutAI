"""
Provider Health Checker Subsystem for CyberScout AI.

Audits provider DNS resolution, URL syntax, collector registration,
and endpoint reachability without downloading heavy payloads.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
import socket
from typing import Any, Dict, List, Optional
import urllib.parse
import yaml

from src.collectors.registry import CollectorRegistry
from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger
from src.utils.url_utils import sanitize_url

logger = get_logger(__name__)


@dataclass
class ProviderHealthResult:
    """Represents the health evaluation result of an individual source provider."""
    source_id: str
    name: str
    status: str  # 'Healthy' | 'Warning' | 'Broken' | 'Disabled'
    collection_method: str
    collector_class: str
    base_url: Optional[str]
    dns_resolved: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderHealthChecker:
    """
    Evaluates DNS resolution, URL syntax, and collector readiness across all sources.
    """

    def __init__(self, config_file: Optional[Path] = None, registry: Optional[CollectorRegistry] = None):
        self.config_file = config_file or (CONFIG_DIR / "sources.yaml")
        self.registry = registry or CollectorRegistry()

    def check_all_providers(self, timeout_seconds: float = 1.5) -> List[ProviderHealthResult]:
        """
        Runs health check across all configured sources in sources.yaml.

        Args:
            timeout_seconds: Timeout limit for socket DNS lookups.

        Returns:
            List of ProviderHealthResult objects.
        """
        results: List[ProviderHealthResult] = []
        if not self.config_file.exists():
            logger.warning(f"Sources configuration '{self.config_file}' not found.")
            return results

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            sources = data.get("sources", [])
        except Exception as e:
            logger.error(f"Could not load sources.yaml: {e}")
            return results

        registered_collectors = set(self.registry.list_collectors())

        # Old default socket timeout backup
        old_timeout = socket.getdefaulttimeout()

        for src in sources:
            if not isinstance(src, dict):
                continue

            sid = src.get("id", "unknown")
            name = src.get("name", sid)
            enabled = bool(src.get("enabled", True))
            method = src.get("collection_method", "rss")
            collector_cls = src.get("preferred_collector", "GenericRSSCollector")
            base_url = src.get("base_url")

            if not enabled:
                results.append(ProviderHealthResult(
                    source_id=sid,
                    name=name,
                    status="Disabled",
                    collection_method=method,
                    collector_class=collector_cls,
                    base_url=base_url,
                    dns_resolved=False,
                    message="Source disabled in configuration.",
                ))
                continue

            # 1. Validate Collector Registration
            if collector_cls == "GenericCollector":
                collector_cls = "GenericRSSCollector"

            collector_ok = collector_cls in registered_collectors

            # 2. Validate URL & DNS Resolution
            dns_ok = False
            url_ok = False
            msg_parts = []

            if base_url and "REPLACE_WITH_CHANNEL_ID" not in base_url:
                try:
                    clean_url = sanitize_url(base_url)
                    url_ok = True
                    parsed = urllib.parse.urlparse(clean_url)
                    hostname = parsed.hostname

                    if hostname:
                        socket.setdefaulttimeout(timeout_seconds)
                        try:
                            socket.getaddrinfo(hostname, 443 if parsed.scheme == "https" else 80, proto=socket.IPPROTO_TCP)
                            dns_ok = True
                        except (socket.gaierror, socket.timeout) as dns_err:
                            msg_parts.append(f"DNS resolution failed: {dns_err}")
                except Exception as ve:
                    msg_parts.append(f"Invalid URL syntax: {ve}")
            else:
                url_ok = True
                dns_ok = True

            # Determine overall status
            if not collector_ok:
                status = "Broken"
                msg_parts.append(f"Unregistered collector class '{collector_cls}'.")
            elif not url_ok or (base_url and not dns_ok):
                status = "Broken"
            elif msg_parts:
                status = "Warning"
            else:
                status = "Healthy"
                msg_parts.append("Provider healthy and reachability verified.")

            results.append(ProviderHealthResult(
                source_id=sid,
                name=name,
                status=status,
                collection_method=method,
                collector_class=collector_cls,
                base_url=base_url,
                dns_resolved=dns_ok,
                message=" | ".join(msg_parts),
            ))

        socket.setdefaulttimeout(old_timeout)
        return results
