"""
Feature 2: Freshness & Decay Engine for CyberScout AI (Phase 12).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class FreshnessAnalyzer:
    """
    Evaluates item age, publication date, decay, and expiration status.
    """

    def __init__(self, max_days_old: int = 90, archive_after_days: int = 60):
        self.max_days_old = max_days_old
        self.archive_after_days = archive_after_days

    def analyze_freshness(
        self,
        published_date_str: Optional[str] = None,
        deadline_str: Optional[str] = None,
        discovered_date_str: Optional[str] = None,
    ) -> Tuple[float, int, Optional[int], str, bool]:
        """
        Calculates freshness score (0 - 100), days_old, days_remaining, status, and expired flag.

        Returns:
            Tuple of (freshness_score, days_old, days_remaining, status_label, is_expired)
        """
        now = datetime.now(timezone.utc)
        ref_date = now

        if published_date_str:
            try:
                dt = datetime.fromisoformat(published_date_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ref_date = dt
            except Exception:
                pass
        elif discovered_date_str:
            try:
                dt = datetime.fromisoformat(discovered_date_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ref_date = dt
            except Exception:
                pass

        days_old = max(0, (now - ref_date).days)
        days_remaining = None
        is_expired = False

        if deadline_str:
            try:
                deadline_dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
                if deadline_dt.tzinfo is None:
                    deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
                diff = (deadline_dt - now).days
                days_remaining = diff
                if diff < 0:
                    is_expired = True
            except Exception:
                pass

        if days_old >= self.archive_after_days:
            is_expired = True

        # Calculate decay freshness score
        if days_old == 0:
            freshness_score = 100.0
        elif days_old >= self.max_days_old:
            freshness_score = 0.0
        else:
            freshness_score = max(0.0, round(100.0 * (1.0 - (days_old / self.max_days_old)), 1))

        if is_expired or freshness_score <= 10.0:
            status_label = "Expired"
        elif days_remaining is not None and days_remaining <= 5:
            status_label = "Expiring Soon"
        elif days_old > 30:
            status_label = "Aging"
        else:
            status_label = "Fresh"

        return freshness_score, days_old, days_remaining, status_label, is_expired
