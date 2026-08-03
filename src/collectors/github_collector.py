"""
GitHub REST API Collector for CyberScout AI.

Searches open-source security repositories, tools, awesome lists, and learning repos.
"""

import os
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.parser_utils import parse_json_content
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


class GithubSearchCollector(BaseCollector):
    """
    Collector querying GitHub REST API for cybersecurity tools and repositories.
    """

    def __init__(self, source_id: str = "github_search", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "GitHub Search Collector"

    def collect(self, task: SearchTask) -> CollectorResult:
        """
        Executes GitHub REST API search query.

        Args:
            task: SearchTask emitted by SearchPlanner.

        Returns:
            CollectorResult containing normalized Opportunity objects.
        """
        target_url = task.target_url
        errors: List[str] = []
        opportunities: List[Dict[str, Any]] = []

        # Optional GitHub Personal Access Token
        token = os.environ.get("GITHUB_TOKEN")
        headers = {}
        if token:
            headers["Authorization"] = f"token {token}"

        try:
            status_code, content = self.context.http_client.get(
                target_url,
                headers=headers,
                source_id=self.source_id,
            )
            if status_code != 200:
                return CollectorResult(
                    source_id=self.source_id,
                    status="failed",
                    errors=[f"GitHub API returned status {status_code} for URL '{target_url}'."],
                )

            payload = parse_json_content(content)
            items = payload.get("items", [])

            for item in items:
                norm = self.normalize_item(item, task)
                if norm:
                    opportunities.append(norm.to_dict())

            return CollectorResult(
                source_id=self.source_id,
                status="success",
                items=opportunities,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"GitHub search collection error: {e}", exc_info=True)
            return CollectorResult(
                source_id=self.source_id,
                status="failed",
                errors=[str(e)],
            )

    def normalize_item(self, item: Dict[str, Any], task: SearchTask) -> Optional[Opportunity]:
        """
        Normalizes a raw GitHub repository item dictionary into canonical Opportunity.

        Args:
            item: Raw repository JSON object from GitHub API.
            task: Associated SearchTask.

        Returns:
            Canonical Opportunity instance.
        """
        name = item.get("full_name") or item.get("name")
        url = item.get("html_url")

        if not name or not url:
            return None

        stars = item.get("stargazers_count", 0)
        desc = item.get("description") or f"GitHub repository {name} (Stars: {stars})"
        topics = item.get("topics", [])

        return Opportunity(
            title=f"{name} (★{stars})",
            url=url,
            source_id=self.source_id,
            description=desc,
            category=OpportunityCategory.GITHUB_REPOSITORY.value,
            provider="GitHub",
            tags=topics[:5],
            published_date=item.get("created_at"),
            status=Status.ACTIVE.value,
            raw_data={
                "stars": stars,
                "forks": item.get("forks_count", 0),
                "language": item.get("language"),
                "license": item.get("license", {}).get("spdx_id") if isinstance(item.get("license"), dict) else None,
            },
        )
