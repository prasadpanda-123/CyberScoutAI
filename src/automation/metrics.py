"""
Metrics tracking for CyberScout AI automation runs.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict


@dataclass
class RunMetrics:
    """Tracks latency metrics for pipeline execution phases."""

    run_id: str
    start_time: float = field(default_factory=time.time)
    planning_time: float = 0.0
    collection_time: float = 0.0
    processing_time: float = 0.0
    ranking_time: float = 0.0
    db_update_time: float = 0.0
    notification_time: float = 0.0
    total_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Returns dictionary of metrics."""
        return {
            "run_id": self.run_id,
            "planning_time_sec": round(self.planning_time, 4),
            "collection_time_sec": round(self.collection_time, 4),
            "processing_time_sec": round(self.processing_time, 4),
            "ranking_time_sec": round(self.ranking_time, 4),
            "db_update_time_sec": round(self.db_update_time, 4),
            "notification_time_sec": round(self.notification_time, 4),
            "total_time_sec": round(self.total_time, 4),
        }
