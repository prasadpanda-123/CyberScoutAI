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
from src.models.opportunity_dto import NormalizedOpportunityDTO

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

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        if task and task.target_url:
            return [task.target_url]
        return ["https://api.github.com/search/repositories?q=cybersecurity+tool&sort=stars&order=desc"]

    def fetch(self, target: str) -> Any:
        token = os.environ.get("GITHUB_TOKEN")
        headers = {}
        if token:
            headers["Authorization"] = f"token {token}"
        status_code, content = self.context.http_client.get(
            target,
            headers=headers,
            source_id=self.source_id,
        )
        if status_code != 200:
            return None
        return content

    def validate(self, raw_data: Any) -> bool:
        if raw_data is None:
            return False
        if isinstance(raw_data, str):
            return len(raw_data.strip()) > 2
        if isinstance(raw_data, (dict, list)):
            return len(raw_data) > 0
        return False

    def parse(self, raw_payload: Any) -> List[Dict[str, Any]]:
        if not raw_payload:
            return []
        payload = parse_json_content(raw_payload)
        return payload.get("items", []) if isinstance(payload, dict) else []

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        full_name = (raw_item.get("full_name") or raw_item.get("name") or "").strip()
        html_url = (raw_item.get("html_url") or raw_item.get("url") or "").strip()
        if not full_name or not html_url:
            return None
        desc = raw_item.get("description") or f"GitHub repository: {full_name}"
        topics = raw_item.get("topics", [])
        from src.models.enums import OpportunityType, PricingType
        return NormalizedOpportunityDTO(
            title=f"Tool: {full_name}",
            url=html_url,
            source_id=self.source_id,
            description=desc,
            provider="GitHub",
            opportunity_type=OpportunityType.OPEN_SOURCE.value,
            categories=["open_source", "security_tool"],
            tags=list(set(["github", "tool"] + topics)),
            pricing_type=PricingType.FREE.value,
            is_free=True,
            raw_payload=raw_item,
        )

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

        try:
            content = self.fetch(target_url)
            if content is None:
                return CollectorResult(
                    source_id=self.source_id,
                    status="failed",
                    errors=[f"GitHub API failed to return data for URL '{target_url}'."],
                )

            items = self.parse(content)
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
