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

    def process_opportunity_batch(self, opportunities: list) -> int:
        """
        Batch evaluates lifecycle states and saves/updates persistent records efficiently.
        """
        if not opportunities:
            return 0

        hashes = [opp.generate_url_hash() for opp in opportunities if opp.generate_url_hash()]
        existing_map = {}
        if hashes:
            for i in range(0, len(hashes), 100):
                chunk = hashes[i:i + 100]
                placeholders = ",".join(["?"] * len(chunk))
                found = self.opp_repo.search(where_clause=f"url_hash IN ({placeholders})", params=tuple(chunk))
                for item in found:
                    existing_map[item.generate_url_hash()] = item

        to_upsert = []
        for opp in opportunities:
            uh = opp.generate_url_hash()
            existing = existing_map.get(uh)
            if existing:
                opp.id = existing.id
                # Preserve existing high-value fields if incoming is missing
                if not opp.deadline and existing.deadline:
                    opp.deadline = existing.deadline
                if not opp.published_date and existing.published_date:
                    opp.published_date = existing.published_date
                if not opp.description and existing.description:
                    opp.description = existing.description
                if (not opp.category or opp.category == "other") and existing.category and existing.category != "other":
                    opp.category = existing.category
                if not opp.provider and existing.provider:
                    opp.provider = existing.provider
                if not opp.company and existing.company:
                    opp.company = existing.company
                if not opp.location and existing.location:
                    opp.location = existing.location
                if (existing.score or 0) > (opp.score or 0):
                    opp.score = existing.score
            to_upsert.append(opp)

        return self.opp_repo.upsert_batch(to_upsert)
