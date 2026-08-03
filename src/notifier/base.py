"""
Base interface and dataclasses for CyberScout AI Notifier.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.models.opportunity import Opportunity


@dataclass
class ReportDigest:
    """Represents data model compiled to render email report."""

    date: str
    total_opportunities: int
    categories: Dict[str, List[Opportunity]] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
