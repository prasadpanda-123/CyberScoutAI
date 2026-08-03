"""
Generic RSS / Atom Feed Collector for CyberScout AI.
"""

from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.parser_utils import parse_rss_xml_content
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


class GenericRSSCollector(BaseCollector):
    """
    Universal RSS 2.0 and Atom feed collector.
    """

    def __init__(self, source_id: str = "generic_rss", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "Generic RSS Collector"

    def collect(self, task: SearchTask) -> CollectorResult:
        """
        Executes RSS collection for target SearchTask URL.

        Args:
            task: SearchTask emitted by SearchPlanner.

        Returns:
            CollectorResult containing normalized Opportunity dictionaries.
        """
        url = task.target_url
        errors: List[str] = []
        opportunities: List[Dict[str, Any]] = []

        try:
            status_code, content = self.context.http_client.get(url, source_id=self.source_id)
            if status_code != 200:
                return CollectorResult(
                    source_id=self.source_id,
                    status="failed",
                    errors=[f"HTTP {status_code} returned for RSS feed '{url}'."],
                )

            raw_items = parse_rss_xml_content(content)
            for item in raw_items:
                normalized = self.normalize_item(item, task)
                if normalized:
                    opportunities.append(normalized.to_dict())

            return CollectorResult(
                source_id=self.source_id,
                status="success",
                items=opportunities,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"RSS collection error for '{url}': {e}", exc_info=True)
            return CollectorResult(
                source_id=self.source_id,
                status="failed",
                errors=[str(e)],
            )

    def normalize_item(self, item: Dict[str, Any], task: SearchTask) -> Optional[Opportunity]:
        """
        Normalizes a raw RSS item dictionary into canonical Opportunity model instance.

        Args:
            item: Raw item dictionary (title, link, description, published_date).
            task: Associated SearchTask.

        Returns:
            Canonical Opportunity instance.
        """
        title = item.get("title", "Untitled").strip()
        url = item.get("link", "").strip() or task.target_url

        if not title or title == "Untitled":
            return None

        cat = task.category if task.category in [c.value for c in OpportunityCategory] else OpportunityCategory.SECURITY_NEWS.value

        return Opportunity(
            title=title,
            url=url,
            source_id=self.source_id,
            description=item.get("description", "").strip(),
            category=cat,
            provider=self.source_id,
            published_date=item.get("published_date"),
            status=Status.ACTIVE.value,
        )
