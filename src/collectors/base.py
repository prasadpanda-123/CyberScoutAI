"""
Abstract Base Collector Contract for CyberScout AI Collection Framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from src.collectors.result import CollectorResult
from src.intelligence.planner_models import SearchTask
from src.models.opportunity_dto import NormalizedOpportunityDTO


class BaseCollector(ABC):
    """
    Abstract Base Class for all CyberScout AI collectors.
    
    Implements the Phase 2 standardized 5-stage contract:
    discover() -> fetch() -> validate() -> parse() -> normalize()
    """

    def __init__(self, source_id: str):
        self.source_id = source_id
        self.is_initialized = False

    @property
    @abstractmethod
    def collector_name(self) -> str:
        """Human-readable display name for the collector."""
        pass

    def initialize(self) -> None:
        """Initializes collector resources (HTTP client, session, dependencies)."""
        self.is_initialized = True

    def discover(self, task: Optional[SearchTask] = None) -> List[str]:
        """
        Discovers candidate endpoints, URLs, or query parameters.
        
        Args:
            task: Optional SearchTask context from planner.
            
        Returns:
            List of target URLs or search targets to harvest.
        """
        if task and task.target_url:
            return [task.target_url]
        return []

    def fetch(self, target: str) -> Any:
        """
        Fetches raw content for a target endpoint with rate limiting and retry backoff.
        
        Args:
            target: Target URL or endpoint.
            
        Returns:
            Raw response payload (text, JSON, XML, or binary).
        """
        if hasattr(self, "context") and getattr(self, "context", None) and hasattr(self.context, "http_client"):
            status_code, content = self.context.http_client.get(target, source_id=self.source_id)
            if status_code == 200:
                return content
            return None
        return None

    def parse(self, raw_payload: Any) -> List[Dict[str, Any]]:
        """
        Parses raw payload into raw candidate items.
        
        Args:
            raw_payload: Unparsed content string/structure from fetch().
            
        Returns:
            List of unnormalized candidate item dictionaries.
        """
        return []

    def validate(self, raw_data: Any) -> bool:
        """
        Validates raw collected payload or item before parsing/normalization.

        Returns:
            True if valid, False otherwise.
        """
        return raw_data is not None

    def normalize(self, raw_item: Dict[str, Any]) -> Union[NormalizedOpportunityDTO, Dict[str, Any]]:
        """
        Normalizes raw item dictionary into canonical NormalizedOpportunityDTO.

        Args:
            raw_item: Individual item dictionary.

        Returns:
            NormalizedOpportunityDTO instance or normalized dictionary.
        """
        if isinstance(raw_item, NormalizedOpportunityDTO):
            return raw_item
        return NormalizedOpportunityDTO(
            title=raw_item.get("title", "Untitled"),
            url=raw_item.get("url", raw_item.get("link", "")),
            source_id=self.source_id,
            description=raw_item.get("description"),
            raw_payload=raw_item,
        )

    def collect(self, task: SearchTask) -> CollectorResult:
        """
        Executes complete collection lifecycle for a planned SearchTask.
        Default template method invoking discover() -> fetch() -> validate() -> parse() -> normalize().

        Args:
            task: Validated SearchTask instance emitted by SearchPlanner.

        Returns:
            Standardized CollectorResult instance.
        """
        targets = self.discover(task)
        items: List[Dict[str, Any]] = []
        errors: List[str] = []

        for target in targets:
            try:
                payload = self.fetch(target)
                if not self.validate(payload):
                    errors.append(f"Payload validation failed for target '{target}'.")
                    continue
                raw_items = self.parse(payload)
                for raw_item in raw_items:
                    normalized = self.normalize(raw_item)
                    if normalized:
                        if hasattr(normalized, "to_dict"):
                            items.append(normalized.to_dict())
                        elif isinstance(normalized, dict):
                            items.append(normalized)
            except Exception as e:
                errors.append(f"Error harvesting target '{target}': {e}")

        status = "success" if not errors else ("partial" if items else "failed")
        return CollectorResult(
            source_id=self.source_id,
            status=status,
            items=items,
            errors=errors,
        )

    def shutdown(self) -> None:
        """Cleans up collector resources on completion or application shutdown."""
        self.is_initialized = False

