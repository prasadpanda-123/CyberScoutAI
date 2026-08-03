"""
Planner and Search Models for CyberScout AI Search Intelligence Layer.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class SearchTemplate:
    """
    Represents a search query template definition.
    """

    category: str
    pattern: str
    weight: float = 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def render(self, keyword: str) -> str:
        """Renders the template pattern with the target keyword."""
        return self.pattern.replace("{keyword}", keyword.strip())

    def to_dict(self) -> Dict[str, Any]:
        """Converts SearchTemplate to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchTemplate":
        """Reconstructs SearchTemplate from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class SearchResultMetadata:
    """
    Metadata attached to a search task or execution result.
    """

    source_name: str
    preferred_collector: str
    rate_limit_rpm: int = 60
    estimated_priority: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchTask:
    """
    Represents a concrete search collection task assigned to a target source.
    """

    source_id: str
    query_text: str
    target_url: str
    category: str
    collection_method: str
    priority: float = 1.0
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Converts SearchTask to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchTask":
        """Reconstructs SearchTask from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class SearchPlan:
    """
    Master execution plan containing structured SearchTasks grouped by source.
    """

    tasks: List[SearchTask] = field(default_factory=list)
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_tasks: int = 0
    sources_targeted: List[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        if self.tasks and not self.total_tasks:
            self.total_tasks = len(self.tasks)
        if self.tasks and not self.sources_targeted:
            self.sources_targeted = sorted(list({t.source_id for t in self.tasks}))

    def get_tasks_for_source(self, source_id: str) -> List[SearchTask]:
        """Returns list of tasks targeting a specific source."""
        return [t for t in self.tasks if t.source_id == source_id]

    def to_dict(self) -> Dict[str, Any]:
        """Converts SearchPlan to dictionary."""
        return {
            "plan_id": self.plan_id,
            "total_tasks": self.total_tasks,
            "sources_targeted": self.sources_targeted,
            "generated_at": self.generated_at,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchPlan":
        """Reconstructs SearchPlan from dictionary."""
        tasks_raw = data.get("tasks", [])
        tasks_objs = [SearchTask.from_dict(t) for t in tasks_raw] if tasks_raw else []
        return cls(
            plan_id=data.get("plan_id", str(uuid.uuid4())),
            total_tasks=data.get("total_tasks", len(tasks_objs)),
            sources_targeted=data.get("sources_targeted", []),
            generated_at=data.get("generated_at", datetime.now(timezone.utc).isoformat()),
            tasks=tasks_objs,
        )


@dataclass
class SearchValidationResult:
    """
    Structured validation output for query and search plan validation.
    """

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Converts SearchValidationResult to dictionary."""
        return asdict(self)
