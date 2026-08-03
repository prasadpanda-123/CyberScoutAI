"""
Statistics and Preferences Models for CyberScout AI.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


@dataclass
class ApplicationStatistics:
    """
    Model representing aggregated operational metrics.
    """

    date: str
    source_id: Optional[str] = None
    category: Optional[str] = None
    count: int = 0
    avg_score: float = 0.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Converts ApplicationStatistics to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplicationStatistics":
        """Reconstructs ApplicationStatistics from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class Preferences:
    """
    Model representing user preferences and engagement overrides.
    """

    key: str
    value: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Converts Preferences to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Preferences":
        """Reconstructs Preferences from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
