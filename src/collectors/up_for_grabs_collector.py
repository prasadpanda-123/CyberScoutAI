"""
Up For Grabs Collector for CyberScout AI (Phase 2).

Harvests open source beginner-friendly projects and issues.
Uses public structured projects manifest: https://up-for-grabs.net/javascripts/projects.json
"""

from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.parser_utils import parse_json_content
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import Difficulty, OpportunityType, PricingType
from src.models.opportunity_dto import NormalizedOpportunityDTO

logger = get_logger(__name__)


class UpForGrabsCollector(BaseCollector):
    """
    Collector fetching beginner-friendly open-source projects from Up For Grabs.
    """

    PROJECTS_JSON_URL = "https://up-for-grabs.net/javascripts/projects.json"

    def __init__(self, source_id: str = "up_for_grabs", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "Up For Grabs Collector"

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        if task and task.target_url:
            return [task.target_url]
        return [self.PROJECTS_JSON_URL]

    def fetch(self, target: str) -> Any:
        status_code, content = self.context.http_client.get(target, source_id=self.source_id)
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
        data = raw_payload if isinstance(raw_payload, (dict, list)) else parse_json_content(raw_payload)
        if isinstance(data, list):
            return data[:25]
        if isinstance(data, dict):
            return data.get("projects", [])[:25]
        return []

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        name = raw_item.get("name", "").strip()
        site = raw_item.get("site", "").strip() or raw_item.get("link", "").strip()
        if not name or not site:
            return None

        desc = raw_item.get("desc", f"Up For Grabs project: {name}")
        tags = raw_item.get("tags", [])

        return NormalizedOpportunityDTO(
            title=f"Open Source: {name}",
            url=site,
            source_id=self.source_id,
            description=desc,
            provider="Up For Grabs Community",
            opportunity_type=OpportunityType.OPEN_SOURCE.value,
            categories=["open_source", "beginner_friendly"],
            tags=["up_for_grabs", "open_source", "good_first_issue"] + tags,
            difficulty=Difficulty.BEGINNER.value,
            pricing_type=PricingType.FREE.value,
            is_free=True,
            raw_payload=raw_item,
        )

    def collect(self, task: SearchTask) -> CollectorResult:
        targets = self.discover(task)
        items: List[Dict[str, Any]] = []
        errors: List[str] = []

        for target in targets:
            try:
                content = self.fetch(target)
                if not self.validate(content):
                    errors.append(f"Validation failed for '{target}'.")
                    continue
                raw_items = self.parse(content)
                for raw_item in raw_items:
                    dto = self.normalize(raw_item)
                    if dto:
                        opp = dto.to_opportunity()
                        items.append(opp.to_dict())
            except Exception as e:
                logger.error(f"Error collecting Up For Grabs from '{target}': {e}", exc_info=True)
                errors.append(str(e))

        status = "success" if not errors else ("partial" if items else "failed")
        return CollectorResult(
            source_id=self.source_id,
            status=status,
            items=items,
            errors=errors,
        )
