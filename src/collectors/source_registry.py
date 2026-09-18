"""
Authoritative Source Registry for CyberScout AI (Phase 2).

Provides programmatic access, lookup, filtering, health tracking integration,
and safe enable/disable controls for all 75 canonical source families.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional

from src.collectors.source_definitions import (
    AUTHORITATIVE_SOURCES,
    RateLimitPolicy,
    SourceDefinition,
)
from src.core.exceptions import CollectorError
from src.core.logging import get_logger

logger = get_logger(__name__)


class SourceRegistry:
    """
    Central Authoritative Registry for CyberScout AI opportunity sources.
    """

    def __init__(self, initial_sources: Optional[Dict[str, SourceDefinition]] = None):
        self._sources: Dict[str, SourceDefinition] = (
            deepcopy(initial_sources) if initial_sources is not None else deepcopy(AUTHORITATIVE_SOURCES)
        )

    def get_source(self, source_id: str) -> Optional[SourceDefinition]:
        """Retrieves a source definition by its canonical machine ID."""
        if not source_id:
            return None
        return self._sources.get(source_id.lower().strip())

    def get_all_sources(self) -> List[SourceDefinition]:
        """Returns list of all 75 registered source definitions."""
        return list(self._sources.values())

    def get_enabled_sources(self) -> List[SourceDefinition]:
        """Returns list of currently enabled source definitions."""
        return [s for s in self._sources.values() if s.enabled]

    def get_sources_by_family(self, family: Any) -> List[SourceDefinition]:
        """Filters sources by SourceFamily taxonomy value."""
        fam_clean = (family.value if hasattr(family, "value") else str(family)).lower().strip()
        return [s for s in self._sources.values() if s.source_family.lower() == fam_clean]

    def get_sources_by_opportunity_type(self, opp_type: Any) -> List[SourceDefinition]:
        """Filters sources supporting a target OpportunityType."""
        type_clean = (opp_type.value if hasattr(opp_type, "value") else str(opp_type)).lower().strip()
        return [
            s for s in self._sources.values()
            if type_clean in [t.lower() for t in s.opportunity_types]
        ]

    def get_sources_by_tier(self, tier: Any) -> List[SourceDefinition]:
        """Filters sources by TrustTier value (tier_1, tier_2, tier_3, tier_4)."""
        tier_clean = (tier.value if hasattr(tier, "value") else str(tier)).lower().strip()
        return [s for s in self._sources.values() if s.trust_tier.lower() == tier_clean]

    def get_sources_by_status(self, status: str) -> List[SourceDefinition]:
        """Filters sources by implementation or review status."""
        status_clean = status.upper().strip()
        return [s for s in self._sources.values() if s.status.upper() == status_clean]

    def is_enabled(self, source_id: str) -> bool:
        """Returns True if the source is registered and enabled."""
        source = self.get_source(source_id)
        return bool(source and source.enabled)

    def set_enabled(self, source_id: str, enabled: bool) -> bool:
        """Sets the enabled status of a registered source."""
        if enabled:
            return self.enable_source(source_id)
        else:
            return self.disable_source(source_id)

    def enable_source(self, source_id: str) -> bool:
        """Safely enables collection for a source."""
        source = self.get_source(source_id)
        if not source:
            raise CollectorError(f"Cannot enable unknown source '{source_id}'.")
        source.enabled = True
        logger.info(f"Source '{source_id}' has been ENABLED.")
        return True

    def disable_source(self, source_id: str) -> bool:
        """Safely disables collection for a source."""
        source = self.get_source(source_id)
        if not source:
            raise CollectorError(f"Cannot disable unknown source '{source_id}'.")
        source.enabled = False
        logger.info(f"Source '{source_id}' has been DISABLED.")
        return True

    def update_source_health(
        self,
        source_id: str,
        health_status: str,
        latency: float = 0.0,
        success: bool = True,
        item_count: int = 0,
        error_class: Optional[str] = None,
    ) -> None:
        """Updates runtime telemetry for a source record."""
        source = self.get_source(source_id)
        if not source:
            return
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        source.last_checked_at = now_iso
        source.health_status = health_status
        source.latency = latency
        if success:
            source.last_success_at = now_iso
            source.success_count += 1
            source.last_item_count = item_count
        else:
            source.last_failure_at = now_iso
            source.failure_count += 1
            if error_class:
                source.error_class = error_class

    def count(self) -> int:
        """Total number of registered sources in catalog."""
        return len(self._sources)
