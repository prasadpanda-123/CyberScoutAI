"""
Notification and Alerting Domain Models for CyberScout AI.

Defines DTOs for persistent outbox records, in-app notification cards,
meaningful change evaluations, and notification events.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from src.models.enums import (
    NotificationChannel,
    NotificationDeliveryMode,
    NotificationEventType,
    NotificationStatus,
)


@dataclass
class MeaningfulChangeDTO:
    """Detailed evaluation of changes between existing record and incoming candidate."""

    is_meaningful: bool
    changed_fields: List[str] = field(default_factory=list)
    change_fingerprint: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NotificationEventDTO:
    """In-memory representation of an actionable notification event."""

    opportunity_id: str
    event_type: NotificationEventType
    title: str
    url: str
    source_id: str
    category: str = "other"
    opportunity_type: Optional[str] = None
    deadline: Optional[str] = None
    price_amount: Optional[float] = None
    stipend_amount: Optional[float] = None
    pricing_type: str = "unknown"
    stipend_type: str = "none"
    remote: bool = False
    location: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    score: float = 0.0
    change_fingerprint: str = ""
    matched_reasons: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NotificationOutboxDTO:
    """Persistent database model for notification outbox records."""

    user_id: Any
    opportunity_id: str
    event_type: str  # 'new', 'updated', 'reopened'
    deduplication_key: str
    id: str = field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:16]}")
    notification_type: str = NotificationChannel.EMAIL.value  # 'email', 'in_app'
    delivery_mode: str = NotificationDeliveryMode.DIGEST.value  # 'immediate', 'digest'
    change_fingerprint: str = ""
    status: str = NotificationStatus.PENDING.value
    is_read: bool = False
    read_at: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    last_error: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    queued_at: Optional[str] = None
    sent_at: Optional[str] = None
    failed_at: Optional[str] = None
    metadata_json: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class NotificationCardDTO:
    """SSR-friendly DTO for rendering user in-app notifications and email alerts."""

    id: str = field(default_factory=lambda: f"card_{uuid.uuid4().hex[:12]}")
    opportunity_id: str = ""
    event_type: Any = "new"  # 'new', 'updated', 'reopened' or NotificationEventType
    title: str = ""
    url: str = ""
    category: str = "general"
    provider: Optional[str] = None
    organization: Optional[str] = None
    deadline: Optional[str] = None
    is_read: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    delivery_mode: str = "digest"
    score: float = 0.0
    remote: bool = False
    match_reasons: List[str] = field(default_factory=list)
    opportunity_type: Optional[str] = None
    view_url: Optional[str] = None
    pricing: Optional[str] = None
    stipend: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    description: Optional[str] = None

    def __post_init__(self):
        if hasattr(self.event_type, "value"):
            self.event_type = self.event_type.value
        self.event_type = str(self.event_type or "new")
        if self.organization and not self.provider:
            self.provider = self.organization
        if self.view_url and not self.url:
            self.url = self.view_url

    @property
    def event_badge_text(self) -> str:
        if self.event_type.lower() == "new":
            return "NEW"
        elif self.event_type.lower() == "updated":
            return "UPDATED"
        elif self.event_type.lower() == "reopened":
            return "REOPENED"
        return self.event_type.upper()

    @property
    def event_badge_css(self) -> str:
        if self.event_type.lower() == "new":
            return "bg-primary/10 text-primary border-primary/20"
        elif self.event_type.lower() == "updated":
            return "bg-warning/10 text-warning border-warning/20"
        elif self.event_type.lower() == "reopened":
            return "bg-success/10 text-success border-success/20"
        return "bg-surface-container text-text-secondary border-border-subtle"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
