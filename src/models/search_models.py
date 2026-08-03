"""
Search Models for CyberScout AI.

Defines SearchQuery and SearchResult models for collectors and search intelligence.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import urllib.parse


@dataclass
class SearchQuery:
    """
    Model representing a collection request query.
    """

    source_id: str = "custom"
    collection_method: str = "rss"
    target_url: str = ""
    query_params: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    category: str = "other"
    query_text: str = ""
    keywords: List[str] = field(default_factory=list)

    def full_url(self) -> str:
        """Returns full URL with query parameters appended."""
        if not self.query_params:
            return self.target_url
        encoded = urllib.parse.urlencode(self.query_params)
        delimiter = "&" if "?" in self.target_url else "?"
        return f"{self.target_url}{delimiter}{encoded}"

    def to_dict(self) -> Dict[str, Any]:
        """Converts SearchQuery to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchQuery":
        """Reconstructs SearchQuery from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class SearchResult:
    """
    Model representing raw results returned by a collector run.
    """

    source_id: str
    raw_items: List[Dict[str, Any]] = field(default_factory=list)
    item_count: int = 0
    status: str = "success"
    error_message: Optional[str] = None
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        if not self.item_count and self.raw_items:
            self.item_count = len(self.raw_items)

    def to_dict(self) -> Dict[str, Any]:
        """Converts SearchResult to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """Reconstructs SearchResult from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
