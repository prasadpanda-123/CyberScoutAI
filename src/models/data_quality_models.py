"""
Strongly typed Data Transfer Objects (DTOs) for Phase 6 Data Quality & Opportunity Lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.models.enums import LifecycleStatus, QualityStatus, FreshnessStatus


@dataclass
class ValidationResultDTO:
    """Outcome of evaluating an opportunity against Data Quality rules."""

    is_valid: bool = True
    quality_status: QualityStatus = QualityStatus.PASSED
    completeness_score: float = 1.0  # [0.0, 1.0]
    quarantine_reason: Optional[str] = None
    missing_fields: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    field_errors: Dict[str, str] = field(default_factory=dict)

    @property
    def is_quarantined(self) -> bool:
        return self.quality_status == QualityStatus.QUARANTINED or bool(self.quarantine_reason)

    @property
    def quarantine_reasons(self) -> List[str]:
        if self.quarantine_reason:
            return [self.quarantine_reason]
        return self.contradictions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "quality_status": self.quality_status.value if hasattr(self.quality_status, "value") else str(self.quality_status),
            "completeness_score": round(self.completeness_score, 4),
            "quarantine_reason": self.quarantine_reason,
            "missing_fields": self.missing_fields,
            "contradictions": self.contradictions,
            "field_errors": self.field_errors,
        }


@dataclass
class LifecycleEvaluationDTO:
    """Outcome of evaluating an opportunity's lifecycle and freshness state."""

    lifecycle_status: LifecycleStatus
    freshness_status: FreshnessStatus
    days_remaining: Optional[int] = None
    days_since_harvest: int = 0
    days_since_change: Optional[int] = None
    is_reopened: bool = False
    is_closing_soon: bool = False
    is_stale: bool = False
    is_severely_stale: bool = False

    @property
    def is_expired(self) -> bool:
        return self.lifecycle_status == LifecycleStatus.EXPIRED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lifecycle_status": self.lifecycle_status.value if hasattr(self.lifecycle_status, "value") else str(self.lifecycle_status),
            "freshness_status": self.freshness_status.value if hasattr(self.freshness_status, "value") else str(self.freshness_status),
            "days_remaining": self.days_remaining,
            "days_since_harvest": self.days_since_harvest,
            "days_since_change": self.days_since_change,
            "is_reopened": self.is_reopened,
            "is_closing_soon": self.is_closing_soon,
            "is_stale": self.is_stale,
            "is_severely_stale": self.is_severely_stale,
        }


@dataclass
class SourceAnomalyReportDTO:
    """Detection report for parser regression and sudden yield drop."""

    source_id: str
    anomaly_detected: bool
    historical_average: float
    current_count: int
    drop_percentage: float
    validation_failure_rate: float
    quarantine_applied: bool = False
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "anomaly_detected": self.anomaly_detected,
            "historical_average": self.historical_average,
            "current_count": self.current_count,
            "drop_percentage": round(self.drop_percentage, 2),
            "validation_failure_rate": round(self.validation_failure_rate, 2),
            "quarantine_applied": self.quarantine_applied,
            "message": self.message,
        }
