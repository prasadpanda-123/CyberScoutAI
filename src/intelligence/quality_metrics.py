"""
Quality Intelligence Metrics Collection & Reporting Module for CyberScout AI.
"""

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class QualityMetrics:
    """
    Tracks statistics for evaluated, accepted, and rejected opportunities.
    """

    evaluated_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    duplicates_removed: int = 0
    spam_attempts_blocked: int = 0
    rejection_reasons: Counter = field(default_factory=Counter)
    detected_keywords: Counter = field(default_factory=Counter)
    detected_topics: Counter = field(default_factory=Counter)
    confidence_distribution: Dict[str, int] = field(default_factory=lambda: {
        "90-100": 0,
        "75-89": 0,
        "60-74": 0,
        "40-59": 0,
        "0-39": 0,
    })

    @property
    def acceptance_rate(self) -> float:
        """Calculates percentage of evaluated items accepted."""
        if self.evaluated_count == 0:
            return 0.0
        return round((self.accepted_count / self.evaluated_count) * 100.0, 1)

    def record_evaluation(
        self,
        accepted: bool,
        confidence_score: float,
        rejection_reason: str = "",
        matched_keywords: List[str] = None,
        matched_topics: List[str] = None,
        is_duplicate: bool = False,
        is_spam: bool = False,
    ) -> None:
        """Records metrics for a single evaluated item."""
        self.evaluated_count += 1
        if accepted:
            self.accepted_count += 1
        else:
            self.rejected_count += 1
            if rejection_reason:
                self.rejection_reasons[rejection_reason] += 1

        if is_duplicate:
            self.duplicates_removed += 1
        if is_spam:
            self.spam_attempts_blocked += 1

        if matched_keywords:
            for kw in matched_keywords:
                self.detected_keywords[kw] += 1

        if matched_topics:
            for top in matched_topics:
                self.detected_topics[top] += 1

        # Confidence distribution binning
        if confidence_score >= 90:
            self.confidence_distribution["90-100"] += 1
        elif confidence_score >= 75:
            self.confidence_distribution["75-89"] += 1
        elif confidence_score >= 60:
            self.confidence_distribution["60-74"] += 1
        elif confidence_score >= 40:
            self.confidence_distribution["40-59"] += 1
        else:
            self.confidence_distribution["0-39"] += 1

    def to_dict(self) -> Dict[str, Any]:
        """Converts metrics instance to dictionary."""
        return {
            "evaluated_count": self.evaluated_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "acceptance_rate": self.acceptance_rate,
            "duplicates_removed": self.duplicates_removed,
            "spam_attempts_blocked": self.spam_attempts_blocked,
            "top_rejection_reasons": dict(self.rejection_reasons.most_common(10)),
            "top_detected_keywords": dict(self.detected_keywords.most_common(10)),
            "top_detected_topics": dict(self.detected_topics.most_common(10)),
            "confidence_distribution": self.confidence_distribution,
        }
