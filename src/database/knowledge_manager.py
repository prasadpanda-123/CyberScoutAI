"""
Knowledge Manager for CyberScout AI.
"""

from typing import Dict, Optional, Tuple

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.models.enums import Status
from src.models.opportunity import Opportunity


class KnowledgeManager:
    """
    Manages persistent opportunity lifecycle states (NEVER_SEEN, SEEN, UPDATED, EXPIRED, ARCHIVED).
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        opp_repo: Optional[OpportunityRepository] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.opp_repo = opp_repo or OpportunityRepository(db_manager=self.db_manager)

    def determine_state(self, opportunity: Opportunity) -> Tuple[str, Optional[Opportunity]]:
        """
        Determines lifecycle state for an Opportunity.

        Args:
            opportunity: Incoming Opportunity object.

        Returns:
            Tuple of (state_string, existing_opp_or_None).
        """
        existing = self.opp_repo.get_by_url_hash(opportunity.generate_url_hash())
        if not existing:
            return "NEVER_SEEN", None

        if existing.status == Status.EXPIRED.value or opportunity.status == Status.EXPIRED.value:
            return "EXPIRED", existing

        if existing.title != opportunity.title or existing.score != opportunity.score:
            return "UPDATED", existing

        return "SEEN_BEFORE", existing

    def process_opportunity_state(self, opportunity: Opportunity) -> str:
        """
        Evaluates state and saves/updates persistent record.

        Args:
            opportunity: Incoming Opportunity object.

        Returns:
            State string.
        """
        state, existing = self.determine_state(opportunity)
        if state == "NEVER_SEEN":
            self.opp_repo.upsert(opportunity)
        elif state in ["UPDATED", "SEEN_BEFORE"]:
            if existing:
                opportunity.id = existing.id
                self.opp_repo.upsert(opportunity)

        return state
