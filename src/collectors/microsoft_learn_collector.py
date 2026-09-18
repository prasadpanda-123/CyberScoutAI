"""
Microsoft Learn Catalog API Collector for CyberScout AI (Phase 2).

Harvests free official courses, training paths, and certifications from Microsoft Learn.
Uses official public endpoint: https://learn.microsoft.com/api/catalog/
"""

from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.parser_utils import parse_json_content
from src.collectors.result import CollectorResult
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTask
from src.models.enums import (
    CertificateAvailable,
    CertificateCost,
    Difficulty,
    OpportunityType,
    PricingType,
)
from src.models.opportunity_dto import NormalizedOpportunityDTO

logger = get_logger(__name__)


class MicrosoftLearnCollector(BaseCollector):
    """
    Collector fetching training modules, learning paths, and certifications from Microsoft Learn.
    """

    CATALOG_API_URL = "https://learn.microsoft.com/api/catalog/"

    def __init__(self, source_id: str = "microsoft_learn", context: Optional[CollectorContext] = None):
        super().__init__(source_id=source_id)
        self.context = context or CollectorContext.create_default()

    @property
    def collector_name(self) -> str:
        return "Microsoft Learn Collector"

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        if task and task.target_url:
            return [task.target_url]
        return [self.CATALOG_API_URL]

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
        items = []
        if isinstance(data, dict):
            # Parse modules
            for mod in data.get("modules", [])[:20]:
                items.append({**mod, "_type": "module"})
            # Parse learning paths
            for lp in data.get("learning_paths", [])[:15]:
                items.append({**lp, "_type": "learning_path"})
        return items

    def normalize(self, raw_item: Dict[str, Any]) -> Optional[NormalizedOpportunityDTO]:
        title = raw_item.get("title", "").strip()
        url = raw_item.get("url", "").strip()
        if not title or not url:
            return None

        levels = raw_item.get("levels", [])
        diff = Difficulty.BEGINNER.value
        if "intermediate" in [l.lower() for l in levels]:
            diff = Difficulty.INTERMEDIATE.value
        elif "advanced" in [l.lower() for l in levels]:
            diff = Difficulty.ADVANCED.value

        duration_mins = raw_item.get("duration_in_minutes")
        duration_str = f"{duration_mins} mins" if duration_mins else None

        opp_type = (
            OpportunityType.CERTIFICATION.value
            if raw_item.get("_type") == "learning_path"
            else OpportunityType.COURSE.value
        )

        uid = str(raw_item.get("uid") or raw_item.get("id") or "").strip() or None
        return NormalizedOpportunityDTO(
            title=title,
            url=url,
            source_id=self.source_id,
            source_external_id=uid,
            description=raw_item.get("summary", f"Microsoft Learn module: {title}"),
            provider="Microsoft Learn",
            opportunity_type=opp_type,
            categories=["course", "certification", "cybersecurity"],
            skills=raw_item.get("roles", []) + raw_item.get("products", []),
            tags=["microsoft", "cloud", "security"] + raw_item.get("roles", []),
            duration=duration_str,
            difficulty=diff,
            pricing_type=PricingType.FREE.value,
            is_free=True,
            certificate_available=CertificateAvailable.YES.value,
            certificate_cost=CertificateCost.FREE.value,
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
                logger.error(f"Error collecting Microsoft Learn from '{target}': {e}", exc_info=True)
                errors.append(str(e))

        status = "success" if not errors else ("partial" if items else "failed")
        return CollectorResult(
            source_id=self.source_id,
            status=status,
            items=items,
            errors=errors,
        )
