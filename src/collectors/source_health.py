"""
Source Health Telemetry & Failure Isolation Engine for CyberScout AI (Phase 2).

Tracks runtime health metrics, consecutive errors, error classifications,
and health status transitions (HEALTHY, DEGRADED, FAILING, DISABLED, MANUAL_REVIEW, UNSUPPORTED).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from src.models.enums import CollectorFailureClass, HealthStatus
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SourceHealthRecord:
    """Telemetry record for a single source's runtime state."""

    source_id: str
    health_status: str = HealthStatus.HEALTHY.value
    parser_version: str = "1.0.0"
    last_attempt: Optional[str] = None
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    failure_count: int = 0
    consecutive_failures: int = 0
    success_count: int = 0
    items_seen: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_rejected: int = 0
    latency: float = 0.0
    error_class: Optional[str] = None
    last_error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceHealthTracker:
    """
    Central telemetry tracker for monitoring and isolating source health.
    """

    def __init__(self, failure_threshold: int = 5):
        self.failure_threshold = failure_threshold
        self._records: Dict[str, SourceHealthRecord] = {}

    def get_or_create_record(self, source_id: str) -> SourceHealthRecord:
        """Retrieves or creates the in-memory health record for a source."""
        sid = source_id.lower().strip()
        if sid not in self._records:
            self._records[sid] = SourceHealthRecord(source_id=sid)
        return self._records[sid]

    def get_record(self, source_id: str) -> Optional[SourceHealthRecord]:
        """Retrieves the in-memory health record if it exists."""
        return self._records.get(source_id.lower().strip())


    def record_attempt(self, source_id: str) -> None:
        """Marks the start of a collection attempt."""
        rec = self.get_or_create_record(source_id)
        rec.last_attempt = datetime.now(timezone.utc).isoformat()

    def record_success(
        self,
        source_id: str,
        latency: float = 0.0,
        items_seen: int = 0,
        items_created: int = 0,
        items_updated: int = 0,
        items_rejected: int = 0,
    ) -> None:
        """Records a successful harvest execution."""
        rec = self.get_or_create_record(source_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        rec.last_success = now_iso
        rec.success_count += 1
        rec.consecutive_failures = 0
        rec.latency = latency
        rec.items_seen += items_seen
        rec.items_created += items_created
        rec.items_updated += items_updated
        rec.items_rejected += items_rejected
        rec.error_class = None
        rec.last_error_message = None

        if rec.health_status not in (
            HealthStatus.DISABLED.value,
            HealthStatus.MANUAL_REVIEW.value,
            HealthStatus.UNSUPPORTED.value,
        ):
            rec.health_status = HealthStatus.HEALTHY.value

        logger.info(
            f"SourceHealth: '{source_id}' SUCCESS (seen={items_seen}, latency={latency:.2f}s, status={rec.health_status})"
        )

    def record_failure(
        self,
        source_id: str,
        error_class: str = CollectorFailureClass.SOURCE_FAILURE.value,
        error_message: str = "",
        latency: float = 0.0,
    ) -> None:
        """Records an isolated source failure without breaking global pipeline execution."""
        rec = self.get_or_create_record(source_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        rec.last_failure = now_iso
        rec.failure_count += 1
        rec.consecutive_failures += 1
        rec.latency = latency
        rec.error_class = error_class
        rec.last_error_message = error_message

        if rec.health_status not in (
            HealthStatus.DISABLED.value,
            HealthStatus.MANUAL_REVIEW.value,
            HealthStatus.UNSUPPORTED.value,
        ):
            if rec.consecutive_failures >= self.failure_threshold:
                rec.health_status = HealthStatus.FAILING.value
            else:
                rec.health_status = HealthStatus.DEGRADED.value

        logger.warning(
            f"SourceHealth: '{source_id}' FAILURE ({error_class}: {error_message}) | "
            f"consecutive_failures={rec.consecutive_failures} | new_status={rec.health_status}"
        )

    def get_health_status(self, source_id: str) -> str:
        """Returns current HealthStatus enum string for a source."""
        rec = self.get_or_create_record(source_id)
        return rec.health_status

    def get_all_records(self) -> List[SourceHealthRecord]:
        """Returns list of all active health records."""
        return list(self._records.values())
