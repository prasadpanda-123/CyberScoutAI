"""
Feature 7: Trend Detector & Skill Analytics Engine for CyberScout AI (Phase 12).
"""

from collections import Counter
from typing import Any, Dict, List, Optional
from src.models.opportunity import Opportunity


class TrendDetector:
    """
    Computes weekly/monthly growth trends across categories, keywords, skills, providers, and companies.
    """

    def __init__(self, window_days: int = 30):
        self.window_days = window_days

    def analyze_trends(self, opportunities: List[Opportunity]) -> Dict[str, Any]:
        """
        Analyzes active opportunities for trends.

        Returns:
            Dictionary of trend analytics (top_skills, top_companies, top_categories, provider_growth).
        """
        category_counter: Counter = Counter()
        provider_counter: Counter = Counter()
        company_counter: Counter = Counter()
        tag_counter: Counter = Counter()

        for opp in opportunities:
            if opp.category:
                category_counter[opp.category] += 1
            if opp.provider:
                provider_counter[opp.provider] += 1
            if opp.company:
                company_counter[opp.company] += 1
            for tag in (opp.tags or []):
                if tag:
                    tag_counter[tag.lower()] += 1

        return {
            "window_days": self.window_days,
            "total_analyzed": len(opportunities),
            "top_skills": dict(tag_counter.most_common(10)),
            "top_companies": dict(company_counter.most_common(10)),
            "top_categories": dict(category_counter.most_common(10)),
            "top_providers": dict(provider_counter.most_common(10)),
        }
