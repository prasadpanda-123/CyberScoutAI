"""
Search Planner for CyberScout AI Search Intelligence Layer.

Orchestrates Keywords + Templates + Sources + QueryBuilder + QueryValidator
to produce a structured, source-mapped SearchPlan for Phase 3 Collectors.
"""

from typing import Any, List, Optional
from urllib.parse import quote_plus

from src.core.logging import get_logger
from src.intelligence.keyword_engine import KeywordEngine
from src.intelligence.planner_models import SearchPlan, SearchTask
from src.intelligence.query_builder import QueryBuilder
from src.intelligence.query_validator import QueryValidator
from src.intelligence.source_registry import SourceRegistry

logger = get_logger(__name__)


def _parse_priority(val: Any) -> float:
    """Parses numeric or string priority ('P0', 'P1', 'P2') into float priority weight."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        v = val.strip().upper()
        if v == "P0":
            return 1.0
        elif v == "P1":
            return 0.8
        elif v == "P2":
            return 0.6
        try:
            return float(v)
        except ValueError:
            pass
    return 1.0


class SearchPlanner:
    """
    Constructs comprehensive SearchPlan execution specifications mapped to target sources.
    """

    def __init__(
        self,
        keyword_engine: Optional[KeywordEngine] = None,
        query_builder: Optional[QueryBuilder] = None,
        source_registry: Optional[SourceRegistry] = None,
        validator: Optional[QueryValidator] = None,
    ):
        self.keyword_engine = keyword_engine or KeywordEngine()
        self.query_builder = query_builder or QueryBuilder(keyword_engine=self.keyword_engine)
        self.source_registry = source_registry or SourceRegistry()
        self.validator = validator or QueryValidator(source_registry=self.source_registry)

    def create_search_plan(
        self,
        categories: Optional[List[str]] = None,
        max_queries_per_category: int = 10,
    ) -> SearchPlan:
        """
        Builds a comprehensive SearchPlan for target opportunity categories.

        Args:
            categories: List of opportunity category strings (e.g. ['internship', 'ctf']).
            max_queries_per_category: Limit queries generated per category.

        Returns:
            Validated SearchPlan containing mapped SearchTasks.
        """
        target_cats = categories or ["internship", "ctf", "course", "certification", "hackathon"]
        tasks: List[SearchTask] = []

        for cat in target_cats:
            # 1. Get active sources supporting this category
            active_sources = self.source_registry.get_sources_for_category(cat)
            if not active_sources:
                # Fallback to all enabled sources if category specific not declared
                active_sources = [s for s in self.source_registry.get_all_sources() if s.get("enabled", True)]

            # 2. Generate dynamic queries for this category
            queries = self.query_builder.generate_queries(category=cat, max_queries=max_queries_per_category)

            # 3. Map queries to sources to create SearchTasks
            for src in active_sources:
                sid = src["id"]
                s_method = src.get("collection_method", src.get("type", "rss"))
                collector = src.get("preferred_collector", "GenericRSSCollector")
                rate_rpm = int(src.get("rate_limit_requests_per_minute", 60))
                prio = _parse_priority(src.get("priority", 1.0))

                for q in queries:
                    target_url = self._format_target_url(sid, s_method, q.query_text, src)
                    task = SearchTask(
                        source_id=sid,
                        query_text=q.query_text,
                        target_url=target_url,
                        category=cat,
                        collection_method=s_method,
                        priority=prio,
                        metadata={
                            "preferred_collector": collector,
                            "rate_limit_rpm": rate_rpm,
                        },
                    )
                    tasks.append(task)

        plan = SearchPlan(tasks=tasks)
        validation = self.validator.validate_plan(plan)
        if not validation.is_valid:
            logger.warning(f"Generated SearchPlan has validation issues: {validation.errors}")

        logger.info(f"SearchPlanner created plan '{plan.plan_id}' with {plan.total_tasks} tasks targeting {len(plan.sources_targeted)} sources.")
        return plan

    def _format_target_url(self, source_id: str, method: str, query_text: str, source_info: dict) -> str:
        """Helper to construct standard target URL endpoint for a search query."""
        encoded_q = quote_plus(query_text)
        if source_id == "github_search":
            return f"https://api.github.com/search/repositories?q={encoded_q}"
        elif source_id == "ctftime":
            return "https://ctftime.org/api/v1/events/"
        elif method == "rss":
            return source_info.get("url", f"https://example.com/rss/{source_id}")
        else:
            return f"https://{source_id}.com/search?q={encoded_q}"
