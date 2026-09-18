"""
Universal HTML Scraper Collector for CyberScout AI.
"""

import re
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.parser_utils import parse_html_content
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import OpportunityCategory
from src.models.opportunity import Opportunity
from src.models.opportunity_dto import NormalizedOpportunityDTO

logger = get_logger(__name__)


class HtmlScraperCollector(BaseCollector):
    """
    Universal HTML BeautifulSoup scraper collector.
    """

    def __init__(self, source_id: str = "generic_html", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "HTML Scraper Collector"

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        if task and task.target_url:
            return [task.target_url]
        return []

    def fetch(self, target: str) -> Any:
        status_code, content = self.context.http_client.get(target, source_id=self.source_id)
        if status_code != 200:
            return None
        return content

    def validate(self, raw_data: Any) -> bool:
        return bool(raw_data and isinstance(raw_data, str) and len(raw_data.strip()) > 20)

    def parse(self, raw_payload: Any) -> List[Dict[str, Any]]:
        if not raw_payload:
            return []
        items = []
        soup = parse_html_content(raw_payload)
        if hasattr(soup, "find_all"):
            for a_tag in soup.find_all("a", href=True):
                title = a_tag.get_text(strip=True)
                href = a_tag["href"]
                if title and len(title) > 5 and href.startswith("http"):
                    items.append({"title": title, "url": href})
        if not items:
            matches = re.findall(r'<a\s+[^>]*href=["\'](http[^"\']+)["\'][^>]*>(.*?)</a>', raw_payload, re.IGNORECASE | re.DOTALL)
            for href, title_raw in matches:
                clean_title = re.sub(r"<[^>]+>", "", title_raw).strip()
                if clean_title and len(clean_title) > 5:
                    items.append({"title": clean_title, "url": href})
        return items

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        title = raw_item.get("title", "").strip()
        url = raw_item.get("url", "").strip()
        if not title or not url:
            return None
        return NormalizedOpportunityDTO(
            title=title,
            url=url,
            source_id=self.source_id,
            description=raw_item.get("description", f"Extracted opportunity: {title}"),
            opportunity_type=raw_item.get("category", "other"),
            raw_payload=raw_item,
        )

    def collect(self, task: SearchTask) -> CollectorResult:
        """
        Executes HTML scraping for target SearchTask URL.

        Args:
            task: SearchTask emitted by SearchPlanner.

        Returns:
            CollectorResult containing extracted Opportunity dictionaries.
        """
        url = task.target_url
        errors: List[str] = []
        opportunities: List[Dict[str, Any]] = []

        try:
            content = self.fetch(url)
            if content is None:
                return CollectorResult(
                    source_id=self.source_id,
                    status="failed",
                    errors=[f"Failed to fetch content for target URL '{url}'."],
                )

            raw_items = self.parse(content)
            for raw_item in raw_items:
                raw_item["category"] = task.category or "other"
                norm_dto = self.normalize(raw_item)
                if norm_dto:
                    opp = norm_dto.to_opportunity()
                    opportunities.append(opp.to_dict())

            return CollectorResult(
                source_id=self.source_id,
                status="success" if opportunities else "partial",
                items=opportunities,
                errors=errors,
            )
        except Exception as e:
            logger.error(f"HTML Scraper collection error for '{url}': {e}", exc_info=True)
            return CollectorResult(
                source_id=self.source_id,
                status="failed",
                errors=[str(e)],
            )
