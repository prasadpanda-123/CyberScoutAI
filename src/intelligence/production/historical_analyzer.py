"""
Feature 6: Historical Lifecycle Analyzer for CyberScout AI (Phase 12).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.models.opportunity import Opportunity


class HistoricalLifecycleAnalyzer:
    """
    Tracks state transitions, view count, update count, status changes, score changes,
    and maintains complete opportunity audit trails.
    """

    def record_change(
        self,
        opportunity_id: str,
        change_type: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Formats historical change entry record."""
        return {
            "opportunity_id": opportunity_id,
            "change_type": change_type,
            "old_value": old_value or "",
            "new_value": new_value or "",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    def analyze_lifecycle_delta(
        self, existing_opp: Opportunity, updated_opp: Opportunity
    ) -> List[Dict[str, Any]]:
        """Generates change audit records comparing existing vs updated opportunity."""
        changes = []
        if existing_opp.status != updated_opp.status:
            changes.append(self.record_change(existing_opp.id, "STATUS_CHANGE", existing_opp.status, updated_opp.status))
        if existing_opp.score != updated_opp.score:
            changes.append(self.record_change(existing_opp.id, "SCORE_CHANGE", str(existing_opp.score), str(updated_opp.score)))
        if existing_opp.category != updated_opp.category:
            changes.append(self.record_change(existing_opp.id, "CATEGORY_CHANGE", existing_opp.category, updated_opp.category))
        if existing_opp.provider != updated_opp.provider:
            changes.append(self.record_change(existing_opp.id, "PROVIDER_CHANGE", existing_opp.provider or "", updated_opp.provider or ""))
        return changes
