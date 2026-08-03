"""
Query and Search Plan Validator for CyberScout AI Search Intelligence Layer.

Validates search queries and plans for duplicates, empty values, invalid templates,
missing keywords, invalid categories, and unsupported sources.
"""

from typing import List, Optional
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchPlan, SearchTask, SearchValidationResult
from src.intelligence.source_registry import SourceRegistry
from src.models.search_models import SearchQuery

logger = get_logger(__name__)


class QueryValidator:
    """
    Validation engine ensuring search query and plan integrity.
    """

    def __init__(self, source_registry: Optional[SourceRegistry] = None):
        self.source_registry = source_registry or SourceRegistry()

    def validate_query(self, query: SearchQuery) -> SearchValidationResult:
        """
        Validates an individual SearchQuery object.

        Args:
            query: Target SearchQuery instance.

        Returns:
            SearchValidationResult containing validation status and error list.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not query.query_text or not query.query_text.strip():
            errors.append("Query text is empty or whitespace.")

        if "{keyword}" in query.query_text:
            errors.append(f"Unrendered template variable found in query string: '{query.query_text}'.")

        if not query.keywords:
            warnings.append("Query has no associated keywords.")

        return SearchValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_count=1,
        )

    def validate_plan(self, plan: SearchPlan) -> SearchValidationResult:
        """
        Validates a complete SearchPlan and its constituent SearchTasks.

        Args:
            plan: Target SearchPlan instance.

        Returns:
            SearchValidationResult summarizing overall validity.
        """
        errors: List[str] = []
        warnings: List[str] = []
        seen_tasks = set()

        if not plan.tasks:
            errors.append("SearchPlan contains zero tasks.")
            return SearchValidationResult(is_valid=False, errors=errors, warnings=warnings, validated_count=0)

        for idx, task in enumerate(plan.tasks):
            # 1. Empty query check
            if not task.query_text or not task.query_text.strip():
                errors.append(f"Task #{idx} ('{task.task_id}'): Query text is empty.")

            # 2. Unrendered template check
            if "{keyword}" in task.query_text:
                errors.append(f"Task #{idx}: Unrendered template string '{task.query_text}'.")

            # 3. Duplicate check
            task_key = (task.source_id, task.query_text.lower().strip())
            if task_key in seen_tasks:
                warnings.append(f"Duplicate task detected for source '{task.source_id}' with query '{task.query_text}'.")
            else:
                seen_tasks.add(task_key)

            # 4. Source support check
            source_info = self.source_registry.get_source(task.source_id)
            if not source_info:
                errors.append(f"Task #{idx}: Source ID '{task.source_id}' is not registered in SourceRegistry.")
            elif not source_info.get("enabled", True):
                errors.append(f"Task #{idx}: Target source '{task.source_id}' is disabled.")

        is_valid = len(errors) == 0
        logger.info(f"QueryValidator validated plan '{plan.plan_id}': valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}.")
        return SearchValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            validated_count=len(plan.tasks),
        )
