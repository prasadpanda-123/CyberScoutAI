"""
Geographic Region Registry and Priority Engine for CyberScout AI.

Manages regional keywords, geographic classification, and search prioritization,
guaranteeing heavy dedicated coverage for India and broad international coverage.
"""

from typing import Dict, List, Optional, Set
from src.discovery.discovery_models import GeographicRegion


class RegionRegistry:
    """
    Central repository for regional keyword matrices, geographic detection,
    and search scheduling priorities.
    """

    # Regional search keywords ensuring comprehensive coverage
    REGION_KEYWORDS: Dict[GeographicRegion, List[str]] = {
        GeographicRegion.INDIA: [
            "India", "Indian", "Bengaluru", "Bangalore", "Hyderabad", "Delhi", "NCR",
            "Noida", "Gurugram", "Gurgaon", "Pune", "Mumbai", "Chennai", "Kolkata",
            "CERT-In", "NCIIPC", "DSCI", "MeitY", "AICTE", "IIT", "NIT", "IIIT",
            "Unstop", "Internshala", "CyberPeace", "nullcon", "c0c0n", "BSides India",
        ],
        GeographicRegion.GLOBAL_REMOTE: [
            "remote", "worldwide", "global", "work from anywhere", "virtual",
            "open to all countries", "international", "any location",
        ],
        GeographicRegion.NORTH_AMERICA: [
            "United States", "USA", "Canada", "North America", "DoD", "CISA", "NSA",
            "NIST", "NSF fellowship", "US Cyber Games", "Collegiate Cyber Defense",
        ],
        GeographicRegion.EUROPE: [
            "Europe", "European Union", "UK", "United Kingdom", "Germany", "France",
            "Netherlands", "Sweden", "Switzerland", "ENISA", "ECSC", "NCSC",
        ],
        GeographicRegion.ASIA: [
            "Asia", "Singapore", "Japan", "South Korea", "Taiwan", "Malaysia",
            "Indonesia", "Philippines", "ASEAN", "GovTech Singapore",
        ],
        GeographicRegion.MIDDLE_EAST: [
            "Middle East", "UAE", "United Arab Emirates", "Dubai", "Abu Dhabi",
            "Saudi Arabia", "Riyadh", "Qatar", "Bahrain", "GISEC", "Black Hat MEA",
        ],
        GeographicRegion.AFRICA: [
            "Africa", "Nigeria", "Kenya", "South Africa", "Egypt", "Ghana", "Rwanda",
            "AfricaHackon", "SheHacks Africa", "Cybersecurity Africa",
        ],
        GeographicRegion.SOUTH_AMERICA: [
            "Latin America", "South America", "Brazil", "Argentina", "Colombia",
            "Chile", "Mexico", "OAS Cybersecurity", "Ciberseguridad",
        ],
        GeographicRegion.OCEANIA: [
            "Australia", "New Zealand", "Sydney", "Melbourne", "Brisbane",
            "Canberra", "Auckland", "ACSC", "AustCyber",
        ],
    }

    # Search Priority Weights (Higher weight = higher allocation in search plan)
    # India receives dedicated Priority 1 weighting
    REGION_PRIORITIES: Dict[GeographicRegion, float] = {
        GeographicRegion.INDIA: 1.0,           # Top Priority: Dedicated coverage
        GeographicRegion.GLOBAL_REMOTE: 0.9,   # High Priority: Available everywhere
        GeographicRegion.NORTH_AMERICA: 0.7,
        GeographicRegion.EUROPE: 0.7,
        GeographicRegion.ASIA: 0.6,
        GeographicRegion.MIDDLE_EAST: 0.5,
        GeographicRegion.AFRICA: 0.5,
        GeographicRegion.SOUTH_AMERICA: 0.5,
        GeographicRegion.OCEANIA: 0.5,
    }

    @classmethod
    def get_keywords(cls, region: GeographicRegion) -> List[str]:
        """Returns list of specialized search keywords for a given region."""
        return cls.REGION_KEYWORDS.get(region, [])

    @classmethod
    def get_priority(cls, region: GeographicRegion) -> float:
        """Returns numeric priority weight for a given region."""
        return cls.REGION_PRIORITIES.get(region, 0.5)

    @classmethod
    def detect_region(cls, text: str, domain: Optional[str] = None) -> GeographicRegion:
        """
        Detects likely geographic scope from title, description text, or top-level domain.
        Defaults to GeographicRegion.GLOBAL_REMOTE if ambiguous.
        """
        if not text and not domain:
            return GeographicRegion.GLOBAL_REMOTE

        # Check domain TLD hints first
        if domain:
            low_domain = domain.lower()
            if low_domain.endswith((".in", ".co.in", ".gov.in", ".nic.in", ".ac.in", ".res.in")):
                return GeographicRegion.INDIA
            if low_domain.endswith((".uk", ".co.uk", ".de", ".fr", ".nl", ".eu", ".ch")):
                return GeographicRegion.EUROPE
            if low_domain.endswith((".gov", ".mil", ".us", ".ca")):
                return GeographicRegion.NORTH_AMERICA
            if low_domain.endswith((".au", ".nz")):
                return GeographicRegion.OCEANIA
            if low_domain.endswith((".sg", ".jp", ".kr", ".tw", ".my", ".id")):
                return GeographicRegion.ASIA
            if low_domain.endswith((".ae", ".sa", ".qa")):
                return GeographicRegion.MIDDLE_EAST
            if low_domain.endswith((".ng", ".ke", ".za", ".eg")):
                return GeographicRegion.AFRICA
            if low_domain.endswith((".br", ".ar", ".co", ".cl", ".mx")):
                return GeographicRegion.SOUTH_AMERICA

        low_text = f" {text.lower()} "

        # India specific check (prioritized)
        india_hits = sum(1 for kw in cls.REGION_KEYWORDS[GeographicRegion.INDIA] if kw.lower() in low_text)
        if india_hits >= 1:
            return GeographicRegion.INDIA

        # Global remote check
        if any(kw in low_text for kw in ("remote", "worldwide", "global", "virtual", "anywhere")):
            return GeographicRegion.GLOBAL_REMOTE

        # Regional score evaluation
        scores: Dict[GeographicRegion, int] = {}
        for region, kws in cls.REGION_KEYWORDS.items():
            if region in (GeographicRegion.INDIA, GeographicRegion.GLOBAL_REMOTE):
                continue
            count = sum(1 for kw in kws if kw.lower() in low_text)
            if count > 0:
                scores[region] = count

        if scores:
            best_region = max(scores.items(), key=lambda item: item[1])[0]
            return best_region

        return GeographicRegion.GLOBAL_REMOTE

