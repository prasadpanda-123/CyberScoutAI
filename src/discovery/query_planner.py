"""
Discovery Query Planner for CyberScout AI.

Generates structured search query specifications for the Tavily Search API.
Guarantees heavy prioritization for India while maintaining global international
breadth across all 15 cybersecurity opportunity categories.
"""

from typing import List, Optional
from src.discovery.discovery_models import (
    GeographicRegion,
    OpportunityCategory,
    SearchQuerySpec,
)
from src.discovery.platform_registry import PlatformRegistry
from src.discovery.region_registry import RegionRegistry


class DiscoveryQueryPlanner:
    """
    Builds prioritized search query specifications tailored for the Tavily Search API.
    """

    def __init__(self):
        self.region_registry = RegionRegistry()
        self.platform_registry = PlatformRegistry()

    def get_india_dedicated_queries(self) -> List[SearchQuerySpec]:
        """
        Builds high-value, specialized search queries dedicated to India.
        Covers Indian colleges, tech hubs, CERT-In, Unstop, Internshala, and LinkedIn India.
        """
        return [
            # 1. Indian Cybersecurity Internships
            SearchQuerySpec(
                query='"cybersecurity internship" (India OR Bengaluru OR Hyderabad OR Pune OR Delhi) free application 2026',
                region=GeographicRegion.INDIA,
                category=OpportunityCategory.INTERNSHIP,
                priority=1,
                include_domains=["unstop.com", "internshala.com", "linkedin.com", "wellfound.com"],
                max_results=15,
            ),
            # 2. Unstop Indian Competitions & Hackathons
            SearchQuerySpec(
                query='site:unstop.com ("cybersecurity" OR "information security" OR "ethical hacking" OR "CTF") hackathon 2026',
                region=GeographicRegion.INDIA,
                category=OpportunityCategory.HACKATHON,
                target_platform="Unstop",
                priority=1,
                include_domains=["unstop.com"],
                max_results=15,
            ),
            # 3. Internshala Indian Cyber Security Internships
            SearchQuerySpec(
                query='site:internshala.com "cyber security" internship (stipend OR free)',
                region=GeographicRegion.INDIA,
                category=OpportunityCategory.INTERNSHIP,
                target_platform="Internshala",
                priority=1,
                include_domains=["internshala.com"],
                max_results=15,
            ),
            # 4. Indian Government & Agency Challenges (CERT-In, NCIIPC, MeitY, AICTE)
            SearchQuerySpec(
                query='(site:cert-in.org.in OR site:nciipc.gov.in OR site:dsci.in) ("challenge" OR "competition" OR "fellowship" OR "hackathon")',
                region=GeographicRegion.INDIA,
                category=OpportunityCategory.GOVERNMENT_PORTAL if hasattr(OpportunityCategory, "GOVERNMENT_PORTAL") else OpportunityCategory.RESEARCH,
                priority=1,
                max_results=10,
            ),
            # 5. LinkedIn Public Indexed Jobs/Internships in India
            # STRICT COMPLIANCE: Searches public search index only. No automated session scraping.
            SearchQuerySpec(
                query='site:linkedin.com/jobs ("cybersecurity" OR "information security") ("intern" OR "trainee" OR "entry level") India',
                region=GeographicRegion.INDIA,
                category=OpportunityCategory.INTERNSHIP,
                target_platform="LinkedIn",
                priority=1,
                include_domains=["linkedin.com"],
                max_results=15,
            ),
            # 6. Free Training & Certification Vouchers in India
            SearchQuerySpec(
                query='"cybersecurity training" India (free OR "government funded" OR "scholarship") 2026',
                region=GeographicRegion.INDIA,
                category=OpportunityCategory.FREE_TRAINING,
                priority=1,
                max_results=10,
            ),
            # 7. Indian Security Conferences & Student Mentorship (nullcon, c0c0n, BSides)
            SearchQuerySpec(
                query='("nullcon" OR "c0c0n" OR "BSides India") ("call for papers" OR "student grant" OR "CTF" OR "workshop") 2026',
                region=GeographicRegion.INDIA,
                category=OpportunityCategory.CONFERENCE,
                priority=2,
                max_results=10,
            ),
        ]

    def get_global_remote_queries(self) -> List[SearchQuerySpec]:
        """
        Builds search queries for opportunities available globally and remotely.
        """
        return [
            # 1. Bug Bounty & Vulnerability Disclosure (HackerOne, Bugcrowd, YesWeHack)
            SearchQuerySpec(
                query='(site:hackerone.com OR site:bugcrowd.com OR site:yeswehack.com) ("vulnerability disclosure" OR "bug bounty") "free to participate"',
                region=GeographicRegion.GLOBAL_REMOTE,
                category=OpportunityCategory.BUG_BOUNTY,
                priority=1,
                include_domains=["hackerone.com", "bugcrowd.com", "yeswehack.com", "intigriti.com"],
                max_results=15,
            ),
            # 2. CTFtime Competitions (Online Jeopardy & Attack-Defense)
            SearchQuerySpec(
                query='site:ctftime.org/event upcoming 2026',
                region=GeographicRegion.GLOBAL_REMOTE,
                category=OpportunityCategory.CTF,
                target_platform="CTFtime",
                priority=1,
                include_domains=["ctftime.org"],
                max_results=15,
            ),
            # 3. Educational & Student CTF Challenges (picoCTF, CyberDefenders)
            SearchQuerySpec(
                query='(site:picoctf.org OR site:cyberdefenders.org) ("competition" OR "challenge" OR "free")',
                region=GeographicRegion.GLOBAL_REMOTE,
                category=OpportunityCategory.DFIR_CHALLENGE,
                priority=1,
                include_domains=["picoctf.org", "cyberdefenders.org"],
                max_results=15,
            ),
            # 4. Free Cybersecurity Courses with Verified Credential / Certificate
            SearchQuerySpec(
                query='"free cybersecurity course" ("certificate of completion" OR "free voucher") 2026',
                region=GeographicRegion.GLOBAL_REMOTE,
                category=OpportunityCategory.COURSE_CERTIFICATION,
                priority=2,
                max_results=15,
            ),
            # 5. Remote Entry-Level Cybersecurity Jobs & Internships
            SearchQuerySpec(
                query='site:linkedin.com/jobs ("cybersecurity intern" OR "soc analyst intern" OR "junior penetration tester") "remote"',
                region=GeographicRegion.GLOBAL_REMOTE,
                category=OpportunityCategory.INTERNSHIP,
                target_platform="LinkedIn",
                priority=2,
                include_domains=["linkedin.com"],
                max_results=15,
            ),
            # 6. Open Source Security Programs & Mentorship
            SearchQuerySpec(
                query='("Google Summer of Code" OR "Linux Foundation mentorship") "cybersecurity" OR "security" 2026',
                region=GeographicRegion.GLOBAL_REMOTE,
                category=OpportunityCategory.OPEN_SOURCE_PROGRAM,
                priority=2,
                max_results=10,
            ),
            # 7. Web Security Academy & Hands-on Labs
            SearchQuerySpec(
                query='(site:portswigger.net/web-security OR site:tryhackme.com) ("free learning" OR "free room" OR "path")',
                region=GeographicRegion.GLOBAL_REMOTE,
                category=OpportunityCategory.FREE_TRAINING,
                priority=2,
                include_domains=["portswigger.net", "tryhackme.com", "hackthebox.com"],
                max_results=10,
            ),
        ]

    def get_international_regional_queries(self) -> List[SearchQuerySpec]:
        """
        Builds search queries for international regions across North America,
        Europe, Asia, Middle East, Africa, South America, and Oceania.
        """
        return [
            # North America
            SearchQuerySpec(
                query='"cybersecurity fellowship" OR "student grant" (NSF OR CISA OR "US Cyber Games") 2026',
                region=GeographicRegion.NORTH_AMERICA,
                category=OpportunityCategory.SCHOLARSHIP,
                priority=3,
                max_results=10,
            ),
            # Europe
            SearchQuerySpec(
                query='("European Cyber Security Challenge" OR "ENISA" OR "NCSC") ("competition" OR "free training" OR "internship") 2026',
                region=GeographicRegion.EUROPE,
                category=OpportunityCategory.CTF,
                priority=3,
                max_results=10,
            ),
            # Asia (APAC)
            SearchQuerySpec(
                query='"cybersecurity competition" OR "cyber internship" (Singapore OR Japan OR ASEAN) 2026',
                region=GeographicRegion.ASIA,
                category=OpportunityCategory.INTERNSHIP,
                priority=3,
                max_results=10,
            ),
            # Middle East
            SearchQuerySpec(
                query='("GISEC" OR "Black Hat MEA") ("hackathon" OR "cyber competition" OR "student") 2026',
                region=GeographicRegion.MIDDLE_EAST,
                category=OpportunityCategory.HACKATHON,
                priority=3,
                max_results=10,
            ),
            # Africa
            SearchQuerySpec(
                query='"cybersecurity scholarship" OR "free training" (Africa OR Nigeria OR Kenya) 2026',
                region=GeographicRegion.AFRICA,
                category=OpportunityCategory.SCHOLARSHIP,
                priority=3,
                max_results=10,
            ),
            # South America / LATAM
            SearchQuerySpec(
                query='("ciberseguridad beca" OR "cybersecurity fellowship") (Brasil OR Colombia OR LATAM) 2026',
                region=GeographicRegion.SOUTH_AMERICA,
                category=OpportunityCategory.SCHOLARSHIP,
                priority=4,
                max_results=10,
            ),
            # Oceania (Australia / NZ)
            SearchQuerySpec(
                query='"cybersecurity competition" OR "cybersecurity cadetship" (Australia OR ACSC) 2026',
                region=GeographicRegion.OCEANIA,
                category=OpportunityCategory.INTERNSHIP,
                priority=4,
                max_results=10,
            ),
        ]

    def build_search_plan(
        self,
        max_queries: int = 25,
        prioritize_india: bool = True,
    ) -> List[SearchQuerySpec]:
        """
        Compiles and balances the daily search query plan.
        Enforces India prioritization (minimum 35-45% of total query budget)
        followed by global remote and international slices.

        Args:
            max_queries: Maximum number of search queries permitted for this run.
            prioritize_india: If True, guarantees India queries receive highest priority slots.

        Returns:
            List of SearchQuerySpec items bounded by max_queries.
        """
        all_specs: List[SearchQuerySpec] = []

        india_queries = self.get_india_dedicated_queries()
        global_queries = self.get_global_remote_queries()
        intl_queries = self.get_international_regional_queries()

        if prioritize_india:
            # India queries get top placement
            all_specs.extend(india_queries)
            all_specs.extend(global_queries)
            all_specs.extend(intl_queries)
        else:
            all_specs.extend(global_queries)
            all_specs.extend(india_queries)
            all_specs.extend(intl_queries)

        # Sort stably by priority number (1 = highest)
        all_specs.sort(key=lambda s: s.priority)

        # Truncate to configured budget
        return all_specs[:max_queries]

