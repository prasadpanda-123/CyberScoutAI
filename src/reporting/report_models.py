"""
Report models and data structures for CyberScout AI Reporting System.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from src.models.opportunity import Opportunity


@dataclass
class ReportSummary:
    """Breakdown summary counts across all opportunity categories."""

    internships: int = 0
    courses: int = 0
    certifications: int = 0
    hackathons: int = 0
    ctfs: int = 0
    scholarships: int = 0
    research: int = 0
    security_news: int = 0
    github_projects: int = 0
    total_opportunities: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "Internships": self.internships,
            "Courses": self.courses,
            "Certifications": self.certifications,
            "Hackathons": self.hackathons,
            "CTFs": self.ctfs,
            "Scholarships": self.scholarships,
            "Research": self.research,
            "Security News": self.security_news,
            "GitHub Projects": self.github_projects,
            "Total Opportunities": self.total_opportunities,
        }


@dataclass
class ReportPayload:
    """Holds structured opportunity data for report generators."""

    date_str: str
    summary: ReportSummary
    categories: Dict[str, List[Opportunity]] = field(default_factory=dict)
    all_opportunities: List[Opportunity] = field(default_factory=list)


@dataclass
class ReportResult:
    """Outcome metadata from ReportManager generation execution."""

    docx_path: Optional[Path] = None
    csv_path: Optional[Path] = None
    generation_time_sec: float = 0.0
    docx_size_bytes: int = 0
    csv_size_bytes: int = 0
    rows_written: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def attachment_paths(self) -> List[Path]:
        paths = []
        if self.docx_path and self.docx_path.exists():
            paths.append(self.docx_path)
        if self.csv_path and self.csv_path.exists():
            paths.append(self.csv_path)
        return paths
