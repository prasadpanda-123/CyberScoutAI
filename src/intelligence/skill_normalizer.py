"""
Skill Normalization & Technology Taxonomy Engine for CyberScout AI (Phase 9).

Provides deterministic, auditable skill normalization, alias resolution,
and technology separation without external dependencies or machine learning.
Guarantees distinct technology boundaries (e.g. Java != JavaScript, C != C++).
"""

from typing import Any, Dict, List, Optional, Set
import re
import json

# Canonical alias mapping: maps common variations, abbreviations, or packaging names
# to authoritative canonical skill identifiers.
CANONICAL_SKILL_ALIASES: Dict[str, str] = {
    # Programming / Scripting Languages
    "python3": "python",
    "py": "python",
    "golang": "go",
    "js": "javascript",
    "ts": "typescript",
    "rb": "ruby",
    "bash scripting": "bash",
    "shell scripting": "bash",
    "sh": "bash",
    "powershell core": "powershell",
    "ps": "powershell",
    "rustlang": "rust",
    # Operating Systems & Environments
    "gnu/linux": "linux",
    "rhel": "red hat enterprise linux",
    "k8s": "kubernetes",
    "k8": "kubernetes",
    "docker containers": "docker",
    # Cloud Providers & Platforms
    "aws cloud": "aws",
    "amazon web services": "aws",
    "azure cloud": "azure",
    "microsoft azure": "azure",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    # Security Tools & Frameworks
    "wireshark network analyzer": "wireshark",
    "burpsuite": "burp suite",
    "burp suite professional": "burp suite",
    "burp": "burp suite",
    "metasploit framework": "metasploit",
    "msf": "metasploit",
    "nmap scanner": "nmap",
    "snort ids": "snort",
    "zeek ids": "zeek",
    "bro": "zeek",
    "splunk enterprise": "splunk",
    "ghidra disassembler": "ghidra",
    "ida pro": "ida",
    "owasp zap": "zap",
    "kali": "kali linux",
    # Networking & Protocols
    "tcp/ip": "networking",
    "tcp ip": "networking",
    "computer networks": "networking",
    "network security": "networking",
    "reverse-engineering": "reverse engineering",
    "reverse eng": "reverse engineering",
    "malware-analysis": "malware analysis",
    "pentesting": "penetration testing",
    "pen testing": "penetration testing",
    "pen-testing": "penetration testing",
    "soc": "security operations center",
    "siem": "siem",
    "incident-response": "incident response",
    "ir": "incident response",
    "threat-hunting": "threat hunting",
    "threat intel": "threat intelligence",
    "cti": "cyber threat intelligence",
}

# Explicit distinct technology guards: ensure similar names are NEVER merged or conflated
DISTINCT_TECHNOLOGY_GUARDS: Set[str] = {
    "java",
    "javascript",
    "c",
    "c++",
    "c#",
    "python",
    "cython",
    "sql",
    "nosql",
    "r",
    "rust",
    "go",
}


def normalize_skill(skill: Optional[str]) -> str:
    """
    Normalizes a skill token into a deterministic, lowercase, trimmed string.

    Rules:
    1. Lowercase and strip leading/trailing whitespace.
    2. Collapse internal multiple whitespace to a single space.
    3. Strip surrounding quotation marks, brackets, or trailing punctuation
       while carefully preserving semantic symbols such as '+', '#', '.', and '-'.
    4. Apply canonical alias mappings where defined.
    5. Preserve distinct technology boundaries (e.g. 'java' is never transformed into 'javascript').
    """
    if not skill:
        return ""

    raw = str(skill).strip().lower()
    if not raw:
        return ""

    # Collapse internal whitespace
    raw = re.sub(r"\s+", " ", raw)

    # Strip surrounding quotation marks, parens, brackets, and common boundary delimiters
    raw = re.sub(r"^[\"\'\(\[\{<]+|[\"\'\)\]\}>,;]+$", "", raw).strip()

    # If the skill starts with '#' but is not C#, strip leading hashtag if used as social tag
    if raw.startswith("#") and raw != "#" and not raw.startswith("#!"):
        raw = raw[1:].strip()

    # Canonical alias resolution
    canonical = CANONICAL_SKILL_ALIASES.get(raw, raw)

    return canonical.strip()


def normalize_skill_list(
    skills: Optional[List[str]],
    max_count: int = 50,
    max_len: int = 50,
) -> List[str]:
    """
    Normalizes, deduplicates, and validates a list of skills.

    Safety Bounds:
    - Each skill token is bounded to max_len characters.
    - Resulting list is bounded to max_count items.
    - Empty, purely punctuation, or invalid tokens are discarded.
    - Preserves deterministic sorted ordering.
    """
    if not skills:
        return []

    seen: Set[str] = set()
    result: List[str] = []

    for item in skills:
        if not item:
            continue
        token = normalize_skill(str(item))
        if not token:
            continue

        # Bound token length to avoid DoS or database overflow
        if len(token) > max_len:
            token = token[:max_len].strip()

        # Discard tokens that have been reduced to empty or non-alphanumeric noise
        # (unless they are recognized symbols like 'c' or 'r')
        if not re.search(r"[a-z0-9]", token):
            continue

        if token not in seen:
            seen.add(token)
            result.append(token)

        if len(result) >= max_count:
            break

    # Return deterministically sorted list
    return sorted(result)


def are_skills_equivalent(skill_a: Optional[str], skill_b: Optional[str]) -> bool:
    """
    Evaluates whether two skill strings represent the same canonical technology.
    Strictly prevents conflating distinct technologies (Java != JavaScript, C != C++).
    """
    norm_a = normalize_skill(skill_a)
    norm_b = normalize_skill(skill_b)

    if not norm_a or not norm_b:
        return False

    return norm_a == norm_b


def extract_opportunity_skills(opp: Any) -> List[str]:
    """
    Extracts, normalizes, and deduplicates all skill tokens declared or tagged
    on an opportunity record.
    """
    skills: List[str] = []

    if isinstance(opp, dict):
        raw_tags = opp.get("tags")
        raw_title = opp.get("title") or ""
        raw_category = opp.get("category") or ""
        raw_type = opp.get("opportunity_type") or ""
    else:
        raw_tags = getattr(opp, "tags", None)
        raw_title = getattr(opp, "title", "") or ""
        raw_category = getattr(opp, "category", "") or ""
        raw_type = getattr(opp, "opportunity_type", "") or ""

    # 1. Ingest explicit tags
    if raw_tags:
        if isinstance(raw_tags, list):
            skills.extend([str(t) for t in raw_tags if t])
        elif isinstance(raw_tags, str):
            try:
                parsed = json.loads(raw_tags)
                if isinstance(parsed, list):
                    skills.extend([str(t) for t in parsed if t])
                else:
                    skills.extend([t.strip() for t in raw_tags.split(",") if t.strip()])
            except Exception:
                skills.extend([t.strip() for t in raw_tags.split(",") if t.strip()])

    return normalize_skill_list(skills)
