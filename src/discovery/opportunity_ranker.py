"""
Deterministic Opportunity Ranking Engine for CyberScout AI (Phase F).

Calculates deterministic priority scores and transparent scoring breakdowns
based on cybersecurity relevance, category importance, regional relevance (India prioritized),
remote availability, deadline urgency, student eligibility, and source domain reliability.
Zero LLM calls. Pure Python business rules.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from src.core.logging import get_logger
from src.discovery.pricing_evidence_validator import PricingEvidenceValidator

logger = get_logger(__name__)

CYBER_KEYWORDS = {
    "security", "cyber", "cybersecurity", "vulnerability", "infosec", "soc",
    "pentest", "penetration", "malware", "threat", "incident", "forensics",
    "cryptography", "encryption", "firewall", "cve", "ctf", "bug bounty",
    "red team", "blue team", "exploit", "appsec", "devsecops", "cloud security",
    "network security", "zero day", "siem", "mitre", "reverse engineering"
}

STUDENT_KEYWORDS = {
    "student", "university", "college", "undergraduate", "graduate", "bachelor",
    "intern", "internship", "fresher", "campus", "scholarship", "fellowship"
}

BEGINNER_KEYWORDS = {
    "beginner", "entry level", "entry-level", "introductory", "no experience required",
    "beginner-friendly", "foundations", "fundamentals", "starter"
}


class OpportunityRanker:
    """
    Deterministic scoring and ranking engine evaluating cybersecurity opportunities.
    """

    def __init__(self):
        self.evidence_validator = PricingEvidenceValidator()

    @staticmethod
    def _parse_deadline_days(deadline_str: Optional[str]) -> Optional[int]:
        """Calculates days remaining until deadline from a date string (YYYY-MM-DD)."""
        if not deadline_str:
            return None
        cleaned = str(deadline_str).strip()[:10]
        try:
            dl_date = datetime.strptime(cleaned, "%Y-%m-%d").date()
            today = datetime.now(timezone.utc).date()
            return (dl_date - today).days
        except Exception:
            return None

    def calculate_score(
        self,
        opportunity_data: Dict[str, Any],
        source_domain: Optional[str] = None,
    ) -> Tuple[int, Dict[str, int]]:
        """
        Calculates a deterministic 0-100+ score and itemized breakdown.

        Args:
            opportunity_data: Dictionary containing opportunity fields.
            source_domain: Optional hostname/domain of source.

        Returns:
            Tuple of (overall_score, breakdown_dict).
        """
        breakdown: Dict[str, int] = {}
        total = 0

        title = str(opportunity_data.get("title") or "")
        desc = str(opportunity_data.get("description") or opportunity_data.get("snippet") or "")
        combined_text = f"{title} {desc}".lower()
        category = str(opportunity_data.get("category") or "other").strip().lower()
        country_or_scope = str(opportunity_data.get("country_or_scope") or "Global").strip().lower()
        is_remote = bool(opportunity_data.get("remote") or opportunity_data.get("is_remote", False))
        domain = source_domain or opportunity_data.get("source_domain") or ""

        # 1. Cybersecurity Relevance (+20 points)
        matched_cyber = [k for k in CYBER_KEYWORDS if k in combined_text]
        if matched_cyber:
            pts = 20 if len(matched_cyber) >= 2 else 15
            total += pts
            breakdown["cybersecurity_relevance"] = pts
        else:
            breakdown["cybersecurity_relevance"] = 5
            total += 5

        # 2. Category Weight (+5 to +15 points)
        cat_weights = {
            "internship": 15,
            "scholarship": 15,
            "fellowship": 15,
            "job": 12,
            "ctf": 12,
            "hackathon": 12,
            "bug_bounty": 10,
            "vdp": 10,
            "course": 10,
            "certification": 10,
            "other": 5,
        }
        cat_pts = cat_weights.get(category, 5)
        total += cat_pts
        breakdown["category_weight"] = cat_pts

        # 3. Regional Relevance — India Prioritized (+5 to +15 points)
        is_india = "india" in country_or_scope or "india" in combined_text or "in" in country_or_scope
        if is_india:
            pts = 15 # Dedicated India priority
            total += pts
            breakdown["regional_relevance_india"] = pts
        elif is_remote or "global" in country_or_scope or "worldwide" in country_or_scope or "remote" in country_or_scope:
            pts = 12 # Globally accessible from India
            total += pts
            breakdown["global_remote_accessibility"] = pts
        else:
            pts = 6 # Valid international intelligence
            total += pts
            breakdown["international_scope"] = pts

        # 4. Remote Availability (+10 points)
        if is_remote:
            total += 10
            breakdown["remote_availability"] = 10

        # 5. Beginner Friendliness (+10 points)
        if any(k in combined_text for k in BEGINNER_KEYWORDS) or opportunity_data.get("beginner_friendly"):
            total += 10
            breakdown["beginner_friendly"] = 10

        # 6. Student Eligibility (+10 points)
        if any(k in combined_text for k in STUDENT_KEYWORDS) or category in ("internship", "scholarship"):
            total += 10
            breakdown["student_eligibility"] = 10

        # 7. Deadline Urgency (+5 to +15 points, or penalty if expired)
        dl_str = opportunity_data.get("deadline")
        days_left = self._parse_deadline_days(dl_str)
        if days_left is not None:
            if days_left < 0:
                total -= 40 # Heavily penalize expired opportunities
                breakdown["deadline_expired_penalty"] = -40
            elif days_left <= 14:
                total += 15 # Urgent
                breakdown["deadline_urgent"] = 15
            elif days_left <= 45:
                total += 10 # Approaching
                breakdown["deadline_upcoming"] = 10
            else:
                total += 5
                breakdown["deadline_distant"] = 5
        else:
            breakdown["deadline_undetermined"] = 0

        # 8. Source Domain Reliability (+5 to +15 points)
        if domain and self.evidence_validator.is_trusted_official_domain(domain):
            total += 15
            breakdown["official_source_trust"] = 15
        elif domain and any(domain.endswith(tld) for tld in [".org", ".ac.in", ".edu.in"]):
            total += 10
            breakdown["institutional_domain"] = 10
        else:
            total += 5
            breakdown["standard_domain"] = 5

        # 9. Data Completeness (+5 to +10 points)
        has_desc = len(desc) >= 80
        has_app_url = bool(opportunity_data.get("application_url") or opportunity_data.get("canonical_url"))
        has_skills = bool(opportunity_data.get("required_skills") or opportunity_data.get("requirements"))
        completeness_pts = (4 if has_desc else 0) + (3 if has_app_url else 0) + (3 if has_skills else 0)
        total += completeness_pts
        breakdown["data_completeness"] = completeness_pts

        # 10. Verified Free-to-Participate (+10 points)
        if opportunity_data.get("free_only_decision") == "APPROVED" or opportunity_data.get("is_free") is True:
            total += 10
            breakdown["verified_free"] = 10

        # Ensure final score is non-negative
        final_score = max(0, total)
        return final_score, breakdown

