"""
Target Platform Registry and Domain Intelligence for CyberScout AI.

Manages definitions, domain mappings, compliance rules, and query site-filters
for all targeted cybersecurity discovery platforms.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse


@dataclass
class PlatformDefinition:
    """Metadata and compliance configuration for an opportunity platform."""

    id: str
    name: str
    primary_domain: str
    supported_domains: List[str]
    category_hints: List[str]
    is_public_indexed: bool = True
    requires_site_restriction: bool = False
    notes: str = ""


class PlatformRegistry:
    """
    Registry of canonical cybersecurity opportunity platforms.
    Maps arbitrary URLs and domains to verified platforms and handles compliance boundaries.
    """

    PLATFORMS: List[PlatformDefinition] = [
        # Bug Bounty & Vulnerability Disclosure
        PlatformDefinition(
            id="hackerone",
            name="HackerOne",
            primary_domain="hackerone.com",
            supported_domains=["hackerone.com"],
            category_hints=["bug_bounty", "vulnerability_disclosure"],
            notes="VDPs and bug bounty programs open to public participation.",
        ),
        PlatformDefinition(
            id="bugcrowd",
            name="Bugcrowd",
            primary_domain="bugcrowd.com",
            supported_domains=["bugcrowd.com"],
            category_hints=["bug_bounty", "vulnerability_disclosure"],
            notes="Bug bounty and vulnerability disclosure programs.",
        ),
        PlatformDefinition(
            id="intigriti",
            name="Intigriti",
            primary_domain="intigriti.com",
            supported_domains=["intigriti.com", "app.intigriti.com"],
            category_hints=["bug_bounty"],
            notes="European and international ethical hacking programs.",
        ),
        PlatformDefinition(
            id="yeswehack",
            name="YesWeHack",
            primary_domain="yeswehack.com",
            supported_domains=["yeswehack.com"],
            category_hints=["bug_bounty", "vulnerability_disclosure"],
            notes="Global bug bounty platform.",
        ),

        # CTF Competitions & Challenges
        PlatformDefinition(
            id="ctftime",
            name="CTFtime",
            primary_domain="ctftime.org",
            supported_domains=["ctftime.org"],
            category_hints=["ctf"],
            notes="Global CTF competition directory and team ratings.",
        ),
        PlatformDefinition(
            id="picoctf",
            name="picoCTF",
            primary_domain="picoctf.org",
            supported_domains=["picoctf.org"],
            category_hints=["ctf", "free_training"],
            notes="Carnegie Mellon free educational cybersecurity competition.",
        ),
        PlatformDefinition(
            id="cyberdefenders",
            name="CyberDefenders",
            primary_domain="cyberdefenders.org",
            supported_domains=["cyberdefenders.org"],
            category_hints=["dfir_challenge", "free_training", "ctf"],
            notes="Blue team, SOC analyst, and DFIR challenges.",
        ),

        # Free Training, Courses & Certifications
        PlatformDefinition(
            id="portswigger",
            name="PortSwigger Web Security Academy",
            primary_domain="portswigger.net",
            supported_domains=["portswigger.net"],
            category_hints=["free_training", "course_certification"],
            notes="Interactive labs and web application security training.",
        ),
        PlatformDefinition(
            id="tryhackme",
            name="TryHackMe",
            primary_domain="tryhackme.com",
            supported_domains=["tryhackme.com"],
            category_hints=["free_training", "course_certification"],
            notes="Hands-on cyber security training rooms (free tier).",
        ),
        PlatformDefinition(
            id="hackthebox",
            name="Hack The Box",
            primary_domain="hackthebox.com",
            supported_domains=["hackthebox.com", "academy.hackthebox.com"],
            category_hints=["free_training", "ctf"],
            notes="Penetration testing labs and free academy modules.",
        ),

        # Career, Jobs & Internships (India & Global)
        PlatformDefinition(
            id="unstop",
            name="Unstop",
            primary_domain="unstop.com",
            supported_domains=["unstop.com"],
            category_hints=["hackathon", "internship", "ctf"],
            notes="Premier Indian collegiate competition, hackathon, and hiring portal.",
        ),
        PlatformDefinition(
            id="internshala",
            name="Internshala",
            primary_domain="internshala.com",
            supported_domains=["internshala.com"],
            category_hints=["internship"],
            notes="India-wide internship opportunities and student hiring.",
        ),
        PlatformDefinition(
            id="linkedin",
            name="LinkedIn",
            primary_domain="linkedin.com",
            supported_domains=["linkedin.com", "www.linkedin.com"],
            category_hints=["internship", "job"],
            notes="Strict compliance: Public search indexing only. No session authentication.",
        ),
        PlatformDefinition(
            id="wellfound",
            name="Wellfound (AngelList)",
            primary_domain="wellfound.com",
            supported_domains=["wellfound.com"],
            category_hints=["internship", "job"],
            notes="Startup security engineering and internship roles.",
        ),
        PlatformDefinition(
            id="indeed",
            name="Indeed",
            primary_domain="indeed.com",
            supported_domains=["indeed.com", "in.indeed.com"],
            category_hints=["internship", "job"],
            notes="Broad career aggregator.",
        ),

        # Open Source & Developer Ecosystem
        PlatformDefinition(
            id="github",
            name="GitHub",
            primary_domain="github.com",
            supported_domains=["github.com"],
            category_hints=["open_source_program", "free_training"],
            notes="Security tools, CTF writeups, awesome lists, and open source mentorship.",
        ),
        PlatformDefinition(
            id="gitlab",
            name="GitLab",
            primary_domain="gitlab.com",
            supported_domains=["gitlab.com"],
            category_hints=["open_source_program"],
            notes="Open source cybersecurity projects and repos.",
        ),
    ]

    @classmethod
    def identify_platform(cls, url: str) -> Optional[str]:
        """
        Identifies platform name from a given candidate URL.
        Returns canonical platform name or None if unlisted (generic domain).
        """
        if not url:
            return None

        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
            if hostname.startswith("www."):
                hostname = hostname[4:]
        except Exception:
            return None

        # Check domain suffix matches
        for platform in cls.PLATFORMS:
            for domain in platform.supported_domains:
                clean_domain = domain.lower()
                if clean_domain.startswith("www."):
                    clean_domain = clean_domain[4:]
                if hostname == clean_domain or hostname.endswith(f".{clean_domain}"):
                    return platform.name

        # Heuristic checks for academic and government sites
        if hostname.endswith((".gov", ".gov.in", ".nic.in", ".mil")):
            return "Government Cybersecurity Portal"
        if hostname.endswith((".edu", ".ac.in", ".ac.uk", ".edu.au")):
            return "University Security Portal"

        return None

    @classmethod
    def get_platform_by_id(cls, platform_id: str) -> Optional[PlatformDefinition]:
        """Retrieves PlatformDefinition by platform ID."""
        for p in cls.PLATFORMS:
            if p.id.lower() == platform_id.lower():
                return p
        return None

    @classmethod
    def is_linkedin_url(cls, url: str) -> bool:
        """Checks if URL belongs to LinkedIn."""
        if not url:
            return False
        try:
            netloc = (urlparse(url).netloc or "").lower()
            return "linkedin.com" in netloc
        except Exception:
            return False

