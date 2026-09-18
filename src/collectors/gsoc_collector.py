"""
Google Summer of Code (GSoC) Collector for CyberScout AI (Phase 2).

Harvests open source mentorship opportunities, student projects, and participating organizations.
Uses official public GSoC program endpoints.
"""

from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.parser_utils import parse_json_content
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import OpportunityType, PricingType, StipendType
from src.models.opportunity_dto import NormalizedOpportunityDTO

logger = get_logger(__name__)


class GSoCCollector(BaseCollector):
    """
    Collector fetching Google Summer of Code mentorship opportunities and organizations.
    """

    DEFAULT_API_URL = "https://summerofcode.withgoogle.com/api/archive/programs/"

    def __init__(self, source_id: str = "google_summer_of_code", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "Google Summer of Code Collector"

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        if task and task.target_url:
            return [task.target_url]
        return [self.DEFAULT_API_URL]

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
            return data
        if isinstance(data, dict):
            return data.get("results", data.get("programs", [data]))
        return []

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        title = raw_item.get("name") or raw_item.get("title") or "Google Summer of Code Mentorship"
        year = raw_item.get("year", "2026")
        url = raw_item.get("url") or f"https://summerofcode.withgoogle.com/programs/{year}"

        slug = str(raw_item.get("slug") or raw_item.get("id") or "").strip() or None
        return NormalizedOpportunityDTO(
            title=f"GSoC: {title}",
            url=url,
            source_id=self.source_id,
            source_external_id=slug,
            description=raw_item.get("description", f"Google Summer of Code {year} Open Source Mentorship Program."),
            provider="Google LLC",
            opportunity_type=OpportunityType.OPEN_SOURCE.value,
            categories=["open_source", "internship", "fellowship"],
            tags=["gsoc", "google", "open_source", "mentorship"],
            pricing_type=PricingType.FREE.value,
            is_free=True,
            stipend_type=StipendType.PAID.value,
            stipend_amount=3000.0,
            stipend_currency="USD",
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
                logger.error(f"Error collecting GSoC from '{target}': {e}", exc_info=True)
                errors.append(str(e))

        status = "success" if not errors else ("partial" if items else "failed")
        return CollectorResult(
            source_id=self.source_id,
            status=status,
            items=items,
            errors=errors,
        )
