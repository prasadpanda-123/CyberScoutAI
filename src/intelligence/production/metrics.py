"""
Production Intelligence Metrics Telemetry Module (Phase 12).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class ProductionMetrics:
    """Telemetry collector for Phase 12 Production Intelligence pipeline."""
    total_evaluated: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    total_duplicates_merged: int = 0
    total_expired_archived: int = 0
    total_dead_links_rejected: int = 0
    sum_confidence: float = 0.0
    sum_quality: float = 0.0
    sum_freshness: float = 0.0

    def record_item(
        self,
        is_accepted: bool,
        confidence: float = 0.0,
        quality: float = 0.0,
        freshness: float = 100.0,
        is_duplicate: bool = False,
        is_expired: bool = False,
        is_dead_link: bool = False,
    ) -> None:
        self.total_evaluated += 1
        if is_accepted:
            self.total_accepted += 1
            self.sum_confidence += confidence
            self.sum_quality += quality
            self.sum_freshness += freshness
        else:
            self.total_rejected += 1

        if is_duplicate:
            self.total_duplicates_merged += 1
        if is_expired:
            self.total_expired_archived += 1
        if is_dead_link:
            self.total_dead_links_rejected += 1

    @property
    def avg_confidence(self) -> float:
        if self.total_accepted == 0:
            return 0.0
        return round(self.sum_confidence / self.total_accepted, 1)

    @property
    def avg_quality(self) -> float:
        if self.total_accepted == 0:
            return 0.0
        return round(self.sum_quality / self.total_accepted, 1)

    @property
    def avg_freshness(self) -> float:
        if self.total_accepted == 0:
            return 0.0
        return round(self.sum_freshness / self.total_accepted, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_evaluated": self.total_evaluated,
            "total_accepted": self.total_accepted,
            "total_rejected": self.total_rejected,
            "total_duplicates_merged": self.total_duplicates_merged,
            "total_expired_archived": self.total_expired_archived,
            "total_dead_links_rejected": self.total_dead_links_rejected,
            "avg_confidence": self.avg_confidence,
            "avg_quality": self.avg_quality,
            "avg_freshness": self.avg_freshness,
        }
