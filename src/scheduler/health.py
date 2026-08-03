"""
Job Health & Execution Metrics for CyberScout AI.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class JobMetrics:
    """
    Data model tracking execution metrics and health status for a scheduled job.
    """

    job_id: str
    status: str = "pending"  # pending, running, success, failed, paused
    last_execution: Optional[str] = None
    next_execution: Optional[str] = None
    last_duration_seconds: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    last_error: Optional[str] = None

    def record_success(self, duration_seconds: float) -> None:
        """Records a successful job execution run."""
        self.status = "success"
        self.last_execution = datetime.now(timezone.utc).isoformat()
        self.last_duration_seconds = duration_seconds
        self.success_count += 1
        self.last_error = None

    def record_failure(self, duration_seconds: float, error_msg: str) -> None:
        """Records a failed job execution run."""
        self.status = "failed"
        self.last_execution = datetime.now(timezone.utc).isoformat()
        self.last_duration_seconds = duration_seconds
        self.failure_count += 1
        self.last_error = error_msg

    def to_dict(self) -> Dict[str, Any]:
        """Converts JobMetrics instance to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobMetrics":
        """Reconstructs JobMetrics instance from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
