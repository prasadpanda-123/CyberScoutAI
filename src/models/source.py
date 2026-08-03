"""
Source Data Model for CyberScout AI.

Represents a target internet intelligence source.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict

from src.models.enums import CollectionMethod, SourceStatus, OpportunityCategory


@dataclass
class Source:
    """
    Model representing a registered opportunity data source.
    """

    id: str
    name: str
    collection_method: str = CollectionMethod.RSS.value
    default_category: str = OpportunityCategory.OTHER.value
    status: str = SourceStatus.ACTIVE.value
    enabled: bool = True
    official: bool = False
    trust_score: float = 1.0
    maintenance_level: str = "stable"
    update_frequency: str = "daily"
    max_requests_per_run: int = 10
    request_delay_ms: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        """Converts Source instance to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Source":
        """Reconstructs Source instance from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
