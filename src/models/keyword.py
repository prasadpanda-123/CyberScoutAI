"""
Keyword Data Model for CyberScout AI.

Represents a taxonomy term or search keyword.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
import uuid


@dataclass
class Keyword:
    """
    Model representing a taxonomy keyword.
    """

    term: str
    domain: str
    id: str = ""
    synonym_of: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Converts Keyword instance to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Keyword":
        """Reconstructs Keyword instance from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
