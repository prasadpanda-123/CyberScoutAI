"""
YouTube Public RSS Collector for CyberScout AI.

Collects public channel video RSS feeds without requiring YouTube Data API keys.
"""

from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity
from src.models.opportunity_dto import NormalizedOpportunityDTO

logger = get_logger(__name__)


class YouTubeRSSCollector(BaseCollector):
    """
    Collector fetching public YouTube Channel RSS feeds.
    """

    def __init__(self, source_id: str = "youtube_rss", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "YouTube RSS Collector"

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
        return self._parse_youtube_atom(raw_payload)

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        title = raw_item.get("title", "Untitled Video").strip()
        url = raw_item.get("link", "").strip()
        if not title or not url:
            return None
        from src.models.enums import OpportunityType, PricingType
        return NormalizedOpportunityDTO(
            title=f"Tutorial: {title}",
            url=url,
            source_id=self.source_id,
            description=raw_item.get("description", ""),
            provider=raw_item.get("author", "YouTube Channel"),
            opportunity_type=OpportunityType.COURSE.value,
            categories=["tutorial", "course"],
            tags=["youtube", "tutorial", "video"],
            start_date=raw_item.get("published_date"),
            pricing_type=PricingType.FREE.value,
            is_free=True,
            raw_payload=raw_item,
        )

    def collect(self, task: SearchTask) -> CollectorResult:
        """
        Executes YouTube RSS collection.

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
                    errors=[f"YouTube RSS feed failed for URL '{target_url}'."],
                )

            raw_entries = self.parse(content)
            for entry in raw_entries:
                norm = self.normalize_item(entry, task)
                if norm:
                    opportunities.append(norm.to_dict())

            return CollectorResult(
                source_id=self.source_id,
                status="success",
                items=opportunities,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"YouTube RSS collection error: {e}", exc_info=True)
            return CollectorResult(
                source_id=self.source_id,
                status="failed",
                errors=[str(e)],
            )

    def _parse_youtube_atom(self, content: str) -> List[Dict[str, Any]]:
        """Parses YouTube Atom XML feed entries."""
        entries = []
        try:
            root = ET.fromstring(content)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "yt": "http://www.youtube.com/xml/schemas/2015",
                "media": "http://search.yahoo.com/mrss/",
            }

            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                published_el = entry.find("atom:published", ns)
                author_el = entry.find("atom:author/atom:name", ns)

                # Media group parsing for thumbnail & description
                media_group = entry.find("media:group", ns)
                description = ""
                thumbnail_url = ""
                if media_group is not None:
                    desc_el = media_group.find("media:description", ns)
                    if desc_el is not None and desc_el.text:
                        description = desc_el.text.strip()
                    thumb_el = media_group.find("media:thumbnail", ns)
                    if thumb_el is not None:
                        thumbnail_url = thumb_el.attrib.get("url", "")

                entries.append({
                    "title": title_el.text.strip() if title_el is not None and title_el.text else "Untitled Video",
                    "link": link_el.attrib.get("href", "") if link_el is not None else "",
                    "published_date": published_el.text.strip() if published_el is not None and published_el.text else "",
                    "author": author_el.text.strip() if author_el is not None and author_el.text else "YouTube Channel",
                    "description": description,
                    "thumbnail_url": thumbnail_url,
                })
            return entries
        except ET.ParseError as pe:
            line, col = pe.position if hasattr(pe, "position") else (None, None)
            from src.core.rss_diagnostics import RSSDiagnosticsManager
            RSSDiagnosticsManager().log_parser_error(
                source_id=self.source_id,
                collector_name=self.collector_name,
                target_url=target_url,
                http_status=200,
                content_type="application/atom+xml",
                payload=content,
                exception_msg=str(pe),
                line=line,
                col=col,
            )
            return entries
        except Exception as e:
            logger.warning(f"Failed to parse YouTube Atom XML: {e}")
            return entries

    def normalize_item(self, item: Dict[str, Any], task: SearchTask) -> Optional[Opportunity]:
        """
        Normalizes a raw YouTube video entry into canonical Opportunity.

        Args:
            item: Parsed video entry dictionary.
            task: Associated SearchTask.

        Returns:
            Canonical Opportunity instance.
        """
        title = item.get("title", "").strip()
        url = item.get("link", "").strip()

        if not title or not url:
            return None

        author = item.get("author", "YouTube Channel")

        return Opportunity(
            title=f"[{author}] {title}",
            url=url,
            source_id=self.source_id,
            description=item.get("description", ""),
            category=OpportunityCategory.COURSE.value,
            provider=author,
            published_date=item.get("published_date"),
            status=Status.ACTIVE.value,
            raw_data={
                "thumbnail_url": item.get("thumbnail_url"),
                "channel_name": author,
            },
        )
