"""
Standardized Collector Result Model for CyberScout AI.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.collectors.metrics import CollectorMetrics


@dataclass
class CollectorResult:
    """
    Standardized result model returned by all collector executions.
    """

    source_id: str
    status: str = "success"  # success, partial, failed
    items: List[Dict[str, Any]] = field(default_factory=list)
    item_count: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        if not self.item_count and self.items:
            self.item_count = len(self.items)

    def to_dict(self) -> Dict[str, Any]:
        """Converts CollectorResult to dictionary."""
        return asdict(self)
