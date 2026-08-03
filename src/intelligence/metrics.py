"""
Ranking Metrics for CyberScout AI.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class RankingMetrics:
    """
    Tracks ranking engine execution performance metrics.
    """

    opportunities_ranked: int = 0
    p0_count: int = 0
    p1_count: int = 0
    p2_count: int = 0
    p3_count: int = 0
    total_duration_seconds: float = 0.0

    def record_ranked(self, priority: str) -> None:
        """Records priority count for a ranked opportunity."""
        self.opportunities_ranked += 1
        p_upper = priority.upper()
        if p_upper == "P0":
            self.p0_count += 1
        elif p_upper == "P1":
            self.p1_count += 1
        elif p_upper == "P2":
            self.p2_count += 1
        else:
            self.p3_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Converts RankingMetrics to dictionary."""
        return asdict(self)
