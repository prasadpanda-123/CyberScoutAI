"""
Search Planner for CyberScout AI Search Intelligence Layer.

Constructs optimal SearchPlan definitions containing SearchTasks
mapped from KeywordEngine and SearchTemplateEngine output.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from src.core.logging import get_logger
from src.intelligence.keyword_engine import KeywordEngine
from src.intelligence.planner_models import SearchPlan, SearchTask
from src.intelligence.query_validator import QueryValidator
from src.intelligence.query_builder import QueryBuilder
from src.intelligence.source_registry import SourceRegistry
from src.utils.url_utils import sanitize_url

logger = get_logger(__name__)


def _parse_priority(prio_val: Any) -> float:
    """Helper to convert string/numeric priority to float."""
    if isinstance(prio_val, (int, float)):
        return float(prio_val)
    if isinstance(prio_val, str):
        val = prio_val.upper().strip()
        if val == "P0":
            return 1.0
        if val == "P1":
            return 2.0
        if val == "P2":
            return 3.0
        if val == "P3":
            return 4.0
        try:
            return float(val)
        except ValueError:
            pass
    return 1.0


class SearchPlanner:
    """
    Orchestrates search execution planning by mapping category queries to available sources.
    """

    def __init__(
        self,
        query_builder: Optional[QueryBuilder] = None,
        source_registry: Optional[SourceRegistry] = None,
        validator: Optional[QueryValidator] = None,
    ):
        self.query_builder = query_builder or QueryBuilder()
        self.source_registry = source_registry or SourceRegistry()
        self.validator = validator or QueryValidator()

    def create_plan(
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

    def create_search_plan(self, categories: Optional[List[str]] = None, max_queries_per_category: int = 10) -> SearchPlan:
        """Backward compatibility alias for create_plan."""
        return self.create_plan(categories=categories, max_queries_per_category=max_queries_per_category)

    def _format_target_url(self, source_id: str, method: str, query_text: str, source_info: dict) -> str:
        """Helper to construct standard target URL endpoint for a search query."""
        encoded_q = quote_plus(query_text)
        base_url = source_info.get("base_url") or source_info.get("url")

        if source_id == "github_search":
            return sanitize_url(f"https://api.github.com/search/repositories?q={encoded_q}")
        elif source_id == "ctftime":
            return sanitize_url("https://ctftime.org/api/v1/events/")
        elif method == "rss" and base_url and "REPLACE_WITH_CHANNEL_ID" not in base_url:
            return sanitize_url(base_url)
        elif base_url and "REPLACE_WITH_CHANNEL_ID" not in base_url:
            if "{keyword}" in base_url or "{query}" in base_url:
                raw = base_url.replace("{keyword}", encoded_q).replace("{query}", encoded_q)
                return sanitize_url(raw)
            delimiter = "&" if "?" in base_url else "?"
            return sanitize_url(f"{base_url}{delimiter}q={encoded_q}")
        else:
            clean_id = source_id.replace("_", "-")
            return sanitize_url(f"https://{clean_id}.com/search?q={encoded_q}")
