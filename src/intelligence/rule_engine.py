"""
Rule Engine for CyberScout AI Intelligence Layer.
"""

from typing import Dict, List

from src.models.enums import OpportunityCategory
from src.models.opportunity import Opportunity
from src.intelligence.deadline_engine import DeadlineEngine
from src.intelligence.provider_engine import ProviderEngine
from src.intelligence.weight_manager import WeightManager


class RuleEngine:
    """
    Evaluates rule conditions against an Opportunity.
    """

    def __init__(
        self,
        weight_manager: WeightManager,
        provider_engine: ProviderEngine,
        deadline_engine: DeadlineEngine,
    ):
        self.weight_manager = weight_manager
        self.provider_engine = provider_engine
        self.deadline_engine = deadline_engine

    def evaluate_rules(self, opportunity: Opportunity) -> Dict[str, bool]:
        """
        Evaluates boolean rules for Opportunity.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Dictionary mapping rule_name -> is_triggered.
        """
        text_lower = f"{opportunity.title} {opportunity.description or ''}".lower()
        dl_status, _ = self.deadline_engine.evaluate_deadline(opportunity.deadline)

        rules_triggered = {
            "is_free": opportunity.paid is False,
            "has_certificate": opportunity.certificate is True,
            "is_remote": opportunity.remote is True,
            "is_beginner_friendly": "beginner" in text_lower or opportunity.beginner_friendly is True,
            "trusted_provider": self.provider_engine.get_provider_bonus(opportunity.provider) > 0,
            "deadline_soon": dl_status in ["URGENT", "UPCOMING"],
            "cybersecurity_related": any(k in text_lower for k in ["security", "cyber", "soc", "pentest", "exploit", "cve"]),
            "programming_related": any(k in text_lower for k in ["python", "golang", "rust", "c++", "script"]),
            "cloud_related": any(k in text_lower for k in ["aws", "azure", "cloud", "gcp", "k8s", "kubernetes"]),
            "ctf_competition": opportunity.category == OpportunityCategory.CTF.value or "ctf" in text_lower,
            "scholarship_grant": opportunity.category == OpportunityCategory.SCHOLARSHIP.value or "scholarship" in text_lower,
            "is_expired": dl_status == "EXPIRED",
        }
        return rules_triggered
