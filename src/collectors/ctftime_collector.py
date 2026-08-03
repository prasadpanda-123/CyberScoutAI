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

        # Add timestamp window params for upcoming events
        now_ts = int(time.time())
        future_ts = now_ts + (30 * 86400)  # Next 30 days
        params = {
            "limit": "20",
            "start": str(now_ts),
            "finish": str(future_ts),
        }

        try:
            status_code, content = self.context.http_client.get(
                target_url,
                params=params,
                source_id=self.source_id,
            )
            if status_code != 200:
                return CollectorResult(
                    source_id=self.source_id,
                    status="failed",
                    errors=[f"CTFtime API returned status {status_code} for URL '{target_url}'."],
                )

            events = parse_json_content(content)
            if isinstance(events, list):
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
