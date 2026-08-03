"""
Ranking Statistics Summary for CyberScout AI.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class RankingStatistics:
    """
    Summary statistics of a ranked batch.
    """

    total_opportunities: int = 0
    average_score: float = 0.0
    highest_score: int = 0
    top_category: str = "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Converts RankingStatistics to dictionary."""
        return asdict(self)
