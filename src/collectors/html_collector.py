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
from src.models.opportunity import Opportunity

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
            status_code, content = self.context.http_client.get(url, source_id=self.source_id)
            if status_code != 200:
                return CollectorResult(
                    source_id=self.source_id,
                    status="failed",
                    errors=[f"HTTP {status_code} returned for target URL '{url}'."],
                )

            soup = parse_html_content(content)
            if hasattr(soup, "find_all"):
                for a_tag in soup.find_all("a", href=True):
                    title = a_tag.get_text(strip=True)
                    href = a_tag["href"]
                    if title and len(title) > 5 and href.startswith("http"):
                        opp = Opportunity(
                            title=title,
                            url=href,
                            source_id=self.source_id,
                            category=task.category or "other",
                        )
                        opportunities.append(opp.to_dict())

            # Fallback regex extraction if soup.find_all yielded zero items
            if not opportunities and content:
                matches = re.findall(r'<a\s+[^>]*href=["\'](http[^"\']+)["\'][^>]*>(.*?)</a>', content, re.IGNORECASE | re.DOTALL)
                for href, title_raw in matches:
                    clean_title = re.sub(r"<[^>]+>", "", title_raw).strip()
                    if clean_title and len(clean_title) > 5:
                        opp = Opportunity(
                            title=clean_title,
                            url=href,
                            source_id=self.source_id,
                            category=task.category or "other",
                        )
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
