"""
Digest Builder for CyberScout AI Notifier.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.models.opportunity import Opportunity
from src.notifier.base import ReportDigest


class DigestBuilder:
    """
    Retrieves active opportunities, filters them, groups by category, and creates stats report models.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None, config_path: Optional[Path] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.opp_repo = OpportunityRepository(db_manager=self.db_manager)
        self.config_path = config_path or (CONFIG_DIR / "email.yaml")
        self.max_items = 20
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads max items configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.max_items = int(data.get("max_items", 20))
            except Exception:
                pass

    def build_digest(self) -> ReportDigest:
        """
        Builds ReportDigest model from active database opportunities.

        Returns:
            Populated ReportDigest.
        """
        # Fetch active opportunities, ordered by score descending
        all_active = self.opp_repo.get_active_opportunities(limit=100)

        # Truncate to max items limit
        opps = all_active[:self.max_items]

        # Group by category
        categories = {}
        high_priority_cnt = 0
        total_score = 0

        for opp in opps:
            cat = opp.category or "uncategorized"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(opp)

            # High priority detection
            if opp.raw_data and opp.raw_data.get("priority") in ["P0", "P1"]:
                high_priority_cnt += 1
            elif opp.score >= 60:
                high_priority_cnt += 1

            total_score += opp.score

        avg_score = round(total_score / len(opps), 2) if opps else 0.0
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        stats = {
            "total_opportunities": len(opps),
            "high_priority_count": high_priority_cnt,
            "average_score": avg_score,
        }

        return ReportDigest(
            date=now_str,
            total_opportunities=len(opps),
            categories=categories,
            stats=stats,
        )
