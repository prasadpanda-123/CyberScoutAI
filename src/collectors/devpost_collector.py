"""
Devpost Hackathon Collector for CyberScout AI (Phase 2).

Harvests active developer hackathons and competitions from Devpost.
Uses public RSS / structured endpoints.
"""

from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.parser_utils import parse_rss_xml_content
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import OpportunityType, PricingType
from src.models.opportunity_dto import NormalizedOpportunityDTO

logger = get_logger(__name__)


class DevpostCollector(BaseCollector):
    """
    Collector fetching hackathons and software competitions from Devpost.
    """

    DEFAULT_FEED_URL = "https://devpost.com/hackathons?format=rss"

    def __init__(self, source_id: str = "devpost", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "Devpost Collector"

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        if task and task.target_url:
            return [task.target_url]
        return [self.DEFAULT_FEED_URL]

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
        return parse_rss_xml_content(
            content=raw_payload,
            source_id=self.source_id,
            url=self.DEFAULT_FEED_URL,
            collector_name=self.collector_name,
            status_code=200,
        )

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        title = raw_item.get("title", "").strip()
        url = raw_item.get("link", "").strip() or raw_item.get("url", "").strip()
        if not title or not url:
            return None

        hack_id = str(raw_item.get("id") or "").strip() or None
        return NormalizedOpportunityDTO(
            title=f"Hackathon: {title}",
            url=url,
            source_id=self.source_id,
            source_external_id=hack_id,
            description=raw_item.get("description", f"Devpost Hackathon: {title}"),
            provider="Devpost",
            opportunity_type=OpportunityType.HACKATHON.value,
            categories=["hackathon", "competition"],
            tags=["devpost", "hackathon", "developer"],
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
                logger.error(f"Error collecting Devpost from '{target}': {e}", exc_info=True)
                errors.append(str(e))

        status = "success" if not errors else ("partial" if items else "failed")
        return CollectorResult(
            source_id=self.source_id,
            status=status,
            items=items,
            errors=errors,
        )
