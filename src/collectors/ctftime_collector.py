"""
CTFTime API Collector for CyberScout AI.

Collects upcoming CTF competitions, jeopardy/attack-defense events, and schedule metadata.
"""

import time
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


class CtftimeCollector(BaseCollector):
    """
    Collector fetching upcoming CTF events from CTFTime REST API.
    """

    def __init__(self, source_id: str = "ctftime", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "CTFtime Collector"

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        target = task.target_url if task and task.target_url else "https://ctftime.org/api/v1/events/"
        return [target]

    def fetch(self, target: str) -> Any:
        now_ts = int(time.time())
        future_ts = now_ts + (30 * 86400)
        params = {
            "limit": "20",
            "start": str(now_ts),
            "finish": str(future_ts),
        }
        status_code, content = self.context.http_client.get(
            target,
            params=params,
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
        events = parse_json_content(raw_payload)
        return events if isinstance(events, list) else []

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        title = raw_item.get("title", "").strip()
        url = raw_item.get("url") or raw_item.get("ctftime_url")
        if not title or not url:
            return None
        fmt = raw_item.get("format", "Jeopardy")
        location = raw_item.get("location", "Online")
        desc = raw_item.get("description") or f"{fmt} CTF event (Location: {location})"
        from src.models.enums import OpportunityType, PricingType
        event_id = str(raw_item.get("id")) if raw_item.get("id") else None
        return NormalizedOpportunityDTO(
            title=f"CTF: {title}",
            url=url,
            source_id=self.source_id,
            source_external_id=event_id,
            description=desc,
            provider="CTFtime",
            opportunity_type=OpportunityType.CTF.value,
            categories=["ctf", "competition", "cybersecurity"],
            tags=[fmt.lower(), "ctf", "competition"],
            start_date=raw_item.get("start"),
            deadline=raw_item.get("finish"),
            pricing_type=PricingType.FREE.value,
            is_free=True,
            raw_payload=raw_item,
        )

    def collect(self, task: SearchTask) -> CollectorResult:
        """
        Executes CTFTime API collection.

        Args:
            task: SearchTask emitted by SearchPlanner.

        Returns:
            CollectorResult containing normalized Opportunity objects.
        """
        target_url = task.target_url or "https://ctftime.org/api/v1/events/"
        errors: List[str] = []
        opportunities: List[Dict[str, Any]] = []

        try:
            content = self.fetch(target_url)
            if content is None:
                return CollectorResult(
                    source_id=self.source_id,
                    status="failed",
                    errors=[f"CTFtime API failed to return data for URL '{target_url}'."],
                )

            events = self.parse(content)
            for event in events:
                norm = self.normalize_item(event, task)
                if norm:
                    opportunities.append(norm.to_dict())

            return CollectorResult(
                source_id=self.source_id,
                status="success",
                items=opportunities,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"CTFtime collection error: {e}", exc_info=True)
            return CollectorResult(
                source_id=self.source_id,
                status="failed",
                errors=[str(e)],
            )

    def normalize_item(self, item: Dict[str, Any], task: SearchTask) -> Optional[Opportunity]:
        """
        Normalizes a raw CTFTime event dictionary into canonical Opportunity.

        Args:
            item: Raw event JSON object from CTFTime API.
            task: Associated SearchTask.

        Returns:
            Canonical Opportunity instance.
        """
        title = item.get("title", "").strip()
        url = item.get("url") or item.get("ctftime_url")

        if not title or not url:
            return None

        weight = item.get("weight", 0.0)
        fmt = item.get("format", "Jeopardy")
        location = item.get("location", "Online")
        desc = item.get("description") or f"{fmt} CTF event (Weight: {weight}, Location: {location})"

        return Opportunity(
            title=f"CTF: {title}",
            url=url,
            source_id=self.source_id,
            description=desc,
            category=OpportunityCategory.HACKATHON.value,  # CTFs mapped to competition/hackathon
            provider="CTFtime",
            tags=[fmt.lower(), "ctf", "competition"],
            published_date=item.get("start"),
            deadline=item.get("finish"),
            paid=False,
            status=Status.ACTIVE.value,
            raw_data={
                "weight": weight,
                "format": fmt,
                "ctftime_url": item.get("ctftime_url"),
                "organizers": [o.get("name") for o in item.get("organizers", []) if isinstance(o, dict)],
            },
        )
