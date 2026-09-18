"""
Authoritative Opportunity Lifecycle & Freshness Engine for CyberScout AI (Phase 6).

Evaluates deterministic lifecycle transitions (ACTIVE, CLOSING_SOON, EXPIRED, CLOSED,
REOPENED, REMOVED) and freshness status (FRESH, AGING, STALE, SEVERELY_STALE) based on
factual deadline, timestamps, and source health evidence.
"""

from datetime import date, datetime, timezone
from typing import Any, Optional, Tuple

from src.core.logging import get_logger
from src.models.data_quality_models import LifecycleEvaluationDTO
from src.models.enums import FreshnessStatus, HealthStatus, LifecycleStatus, Status
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


class LifecycleEngine:
    """
    Evaluates and manages deterministic lifecycle and freshness state transitions.
    """

    def __init__(
        self,
        closing_soon_days: int = 3,
        stale_harvest_days: int = 7,
        severely_stale_days: int = 30,
        removal_absence_threshold: int = 3,
    ):
        self.closing_soon_days = closing_soon_days
        self.stale_harvest_days = stale_harvest_days
        self.severely_stale_days = severely_stale_days
        self.removal_absence_threshold = removal_absence_threshold

    def evaluate(self, opp: Opportunity, existing: Optional[Opportunity] = None, source_health_status: Optional[str] = None, current_date: Optional[date] = None) -> LifecycleEvaluationDTO:
        """Convenience alias for evaluate_lifecycle."""
        return self.evaluate_lifecycle(opp, existing=existing, source_health_status=source_health_status, current_date=current_date)

    def evaluate_freshness(self, opp: Opportunity) -> FreshnessStatus:
        """Convenience helper returning the FreshnessStatus directly."""
        return self.evaluate_lifecycle(opp).freshness_status

    def evaluate_lifecycle(
        self,
        opp: Opportunity,
        existing: Optional[Opportunity] = None,
        source_health_status: Optional[str] = None,
        current_date: Optional[date] = None,
    ) -> LifecycleEvaluationDTO:
        """
        Evaluates lifecycle and freshness states for an opportunity.

        Args:
            opp: Incoming or candidate Opportunity instance.
            existing: Existing canonical database Opportunity, if any.
            source_health_status: Health status of the parent source ('healthy', 'degraded', etc.).
            current_date: Optional reference date (defaults to UTC today).

        Returns:
            LifecycleEvaluationDTO containing lifecycle_status, freshness_status,
            days_remaining, and transition flags.
        """
        if current_date is None:
            current_date = datetime.now(timezone.utc).date()

        days_remaining: Optional[int] = None
        is_reopened = False
        is_closing_soon = False
        is_stale = False
        is_severely_stale = False

        # -------------------------------------------------------------
        # 1. DEADLINE-DRIVEN LIFECYCLE EVALUATION
        # -------------------------------------------------------------
        deadline_obj: Optional[date] = None
        if opp.deadline:
            dl_str = str(opp.deadline).strip()
            try:
                deadline_obj = datetime.strptime(dl_str[:10], "%Y-%m-%d").date()
            except Exception:
                pass

        # Check existing status for REOPENED transition
        existing_status = (existing.lifecycle_status if existing and hasattr(existing, "lifecycle_status")
                           else (existing.status if existing else "")).lower()

        if deadline_obj:
            days_remaining = (deadline_obj - current_date).days

            if days_remaining < 0:
                lifecycle_status = LifecycleStatus.EXPIRED
            elif 0 <= days_remaining <= self.closing_soon_days:
                lifecycle_status = LifecycleStatus.CLOSING_SOON
                is_closing_soon = True
            else:
                lifecycle_status = LifecycleStatus.ACTIVE

            # Check if previously closed/expired opportunity has reopened with future deadline
            if existing_status in ("expired", "closed", "archived") and days_remaining >= 0:
                is_reopened = True
        else:
            # Deadline unspecified: preserve active or existing status
            if existing_status == "closed":
                lifecycle_status = LifecycleStatus.CLOSED
            elif existing_status == "removed":
                lifecycle_status = LifecycleStatus.REMOVED
            else:
                lifecycle_status = LifecycleStatus.ACTIVE

        # Check for explicit source closure signal
        opp_status = (opp.status or "").lower()
        if opp_status in ("closed", "filled", "cancelled"):
            lifecycle_status = LifecycleStatus.CLOSED

        # -------------------------------------------------------------
        # 2. FRESHNESS & STALE DATA EVALUATION
        # -------------------------------------------------------------
        days_since_harvest = 0
        ref_harvest = opp.last_harvested_at or (existing.last_harvested_at if existing else None) or opp.first_seen_at
        if ref_harvest:
            try:
                if isinstance(ref_harvest, datetime):
                    h_date = ref_harvest.date()
                elif isinstance(ref_harvest, date):
                    h_date = ref_harvest
                else:
                    h_date = datetime.fromisoformat(str(ref_harvest).replace("Z", "+00:00")).date()
                days_since_harvest = max(0, (current_date - h_date).days)
            except Exception:
                days_since_harvest = 0

        days_since_change: Optional[int] = None
        ref_change = opp.last_changed_at or (existing.last_changed_at if existing else None)
        if ref_change:
            try:
                if isinstance(ref_change, datetime):
                    c_date = ref_change.date()
                elif isinstance(ref_change, date):
                    c_date = ref_change
                else:
                    c_date = datetime.fromisoformat(str(ref_change).replace("Z", "+00:00")).date()
                days_since_change = max(0, (current_date - c_date).days)
            except Exception:
                pass

        # Evaluate freshness status
        clean_health = (source_health_status or "healthy").lower().strip()

        if days_since_harvest > self.severely_stale_days or clean_health in ("disabled", "failing"):
            freshness_status = FreshnessStatus.SEVERELY_STALE
            is_severely_stale = True
            is_stale = True
        elif days_since_harvest > self.stale_harvest_days or clean_health in ("degraded", "manual_review"):
            freshness_status = FreshnessStatus.STALE
            is_stale = True
        elif days_since_harvest > 3:
            freshness_status = FreshnessStatus.AGING
        else:
            freshness_status = FreshnessStatus.FRESH

        return LifecycleEvaluationDTO(
            lifecycle_status=lifecycle_status,
            freshness_status=freshness_status,
            days_remaining=days_remaining,
            days_since_harvest=days_since_harvest,
            days_since_change=days_since_change,
            is_reopened=is_reopened,
            is_closing_soon=is_closing_soon,
            is_stale=is_stale,
            is_severely_stale=is_severely_stale,
        )

    def evaluate_removal(self, existing: Opportunity, was_in_harvest: bool) -> Tuple[bool, int]:
        """
        Evaluates safe disappearance policy when a source completes a successful harvest.

        Returns:
            Tuple of (is_removed: bool, new_absence_count: int).
        """
        current_absences = getattr(existing, "absence_count", 0) or 0
        if was_in_harvest:
            # Present in harvest -> reset absence count
            return False, 0

        # Missing from harvest -> increment absence count
        new_absences = current_absences + 1
        is_removed = new_absences >= self.removal_absence_threshold
        return is_removed, new_absences
