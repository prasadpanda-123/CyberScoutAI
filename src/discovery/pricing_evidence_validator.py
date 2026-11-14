"""
Pricing Evidence Validator for Free-Only Verification (Phase E).

Verifies pricing statements and evidence excerpts against raw page content,
checks domain source trust hierarchies, detects financial contradictions,
and separates participant costs from participant compensation.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.logging import get_logger
from src.discovery.free_only_models import FinancialDimension, VerifiedPricingEvidence

logger = get_logger(__name__)

# Mandatory fee indicators (violates free-only policy if mandatory for participation)
MANDATORY_FEE_PATTERNS = [
    (r"\b(?:application|entry|submission)\s+fee(?:\s+is|\s+of|\s*:)?\s*(?:\$|₹|€|£|usd|inr|eur)?\s*([1-9][0-9]*)", FinancialDimension.APPLICATION_FEE),
    (r"\b(?:registration|participat\w+)\s+fee(?:\s+is|\s+of|\s*:)?\s*(?:\$|₹|€|£|usd|inr|eur)?\s*([1-9][0-9]*)", FinancialDimension.REGISTRATION_FEE),
    (r"\b(?:tuition|course\s+fee|bootcamp\s+fee)(?:\s+is|\s+of|\s*:)?\s*(?:\$|₹|€|£|usd|inr|eur)?\s*([1-9][0-9]*)", FinancialDimension.TUITION_OR_COURSE_FEE),
    (r"\bmandatory\s+(?:certification|exam(?:ination)?)\s+fee", FinancialDimension.MANDATORY_CERTIFICATION),
    (r"\bmandatory\s+(?:membership|paid\s+subscription|purchase)", FinancialDimension.MANDATORY_MEMBERSHIP),
    (r"\bfee(?:\s+of|\s*:)?\s*(?:\$|₹|€|£|usd|inr)\s*([1-9][0-9]*(?:,\d{3})*(?:\.\d{2})?)", FinancialDimension.GENERAL_PARTICIPATION),
]

# Free participation affirmative indicators
FREE_INDICATORS = [
    r"\b100%\s+free\b",
    r"\bcompletely\s+free\b",
    r"\bfree\s+of\s+cost\b",
    r"\bno\s+application\s+fee\b",
    r"\bno\s+registration\s+fee\b",
    r"\bno\s+fees?\s+required\b",
    r"\bfree\s+admission\b",
    r"\bfree\s+to\s+apply\b",
    r"\bfree\s+to\s+participate\b",
    r"\bfree\s+entry\b",
    r"\bfree\s+registration\b",
    r"\bfree\s+training\b",
    r"\bfree\s+course\b",
    r"\bfully\s+funded\b",
]

# Compensation indicators (money paid TO the applicant/participant, NOT a cost)
COMPENSATION_PATTERNS = [
    r"\b(?:stipend|salary|compensation|remuneration|allowance)(?:\s+of|\s*:)?\s*(?:\$|₹|€|£|usd|inr)?\s*([0-9]+(?:,[0-9]{3})*)",
    r"\b(?:prize\s+pool|cash\s+prizes?|bounty\s+rewards?)(?:\s+of|\s*:)?\s*(?:\$|₹|€|£|usd|inr)?\s*([0-9]+(?:,[0-9]{3})*)",
    r"\bhourly\s+rate\s+of\s+(?:\$|₹|€|£)\s*[0-9]+",
    r"\bpaid\s+internship\b",
    r"\bpaid\s+fellowship\b",
    r"\bcompetitive\s+salary\b",
]

# Optional fee indicators (does not disqualify an otherwise free opportunity)
OPTIONAL_PATTERNS = [
    r"\boptional\s+(?:verified\s+)?certificate\b",
    r"\boptional\s+(?:paid\s+)?exam(?:ination)?\b",
    r"\boptional\s+upgrade\b",
    r"\baudit\s+(?:for\s+)?free\b",
    r"\bfree\s+to\s+audit\b",
    r"\bfree\s+course(?:\s+with\s+optional\s+certificate)?\b",
]

# Trusted official domains (higher confidence in source validity)
HIGH_TRUST_TLDS = (".gov", ".gov.in", ".edu", ".edu.in", ".ac.in", ".mil")
TRUSTED_SECURITY_DOMAINS = {
    "hackerone.com", "bugcrowd.com", "intigriti.com", "yeswehack.com",
    "ctftime.org", "unstop.com", "cert-in.org.in", "nciipc.gov.in",
    "sans.org", "isaca.org", "isc2.org", "owasp.org", "cisa.gov",
}


def _normalize(text: str) -> str:
    """Collapses whitespace and lowercases text for verbatim substring checks."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


class PricingEvidenceValidator:
    """
    Validates economic claims and supporting excerpts against source page evidence.
    """

    def verify_excerpt_in_content(self, excerpt: str, page_content: str) -> bool:
        """Verifies that an excerpt exists verbatim in the extracted page content."""
        if not excerpt or not page_content:
            return False
        clean_excerpt = _normalize(excerpt)
        clean_content = _normalize(page_content)
        if len(clean_excerpt) < 5:
            return False
        if clean_excerpt in clean_content:
            return True
        # Punctuation-insensitive fallback
        clean_excerpt_alpha = re.sub(r"[^\w\s]", "", clean_excerpt)
        clean_content_alpha = re.sub(r"[^\w\s]", "", clean_content)
        return clean_excerpt_alpha in clean_content_alpha

    def scan_for_mandatory_fees(self, page_content: str) -> List[Tuple[str, str, FinancialDimension]]:
        """
        Scans content for affirmative mandatory participant fees.
        Returns list of (matched_sentence, fee_amount, dimension).
        """
        findings: List[Tuple[str, str, FinancialDimension]] = []
        if not page_content:
            return findings

        # First check if optional fee covers it
        sentences = re.split(r"[.\n;]", page_content)
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            # If the sentence explicitly states it is optional, skip mandatory fee flag
            if any(re.search(pat, s_clean, re.IGNORECASE) for pat in OPTIONAL_PATTERNS):
                continue

            # Check if this sentence is compensation/prize money rather than fee
            if any(re.search(pat, s_clean, re.IGNORECASE) for pat in COMPENSATION_PATTERNS):
                # Ensure it's not a dual statement like "stipend of $1000, application fee $50"
                if not re.search(r"application\s+fee|registration\s+fee", s_clean, re.IGNORECASE):
                    continue

            for pattern, dimension in MANDATORY_FEE_PATTERNS:
                m = re.search(pattern, s_clean, re.IGNORECASE)
                if m:
                    amt = m.group(1) if m.groups() else ""
                    findings.append((s_clean, amt, dimension))
                    break

        return findings

    def scan_for_free_evidence(self, page_content: str) -> List[str]:
        """Scans content for affirmative explicit free statements."""
        findings: List[str] = []
        if not page_content:
            return findings
        for pattern in FREE_INDICATORS:
            for m in re.finditer(pattern, page_content, re.IGNORECASE):
                # Extract surrounding sentence context
                start = max(0, m.start() - 40)
                end = min(len(page_content), m.end() + 60)
                snippet = page_content[start:end].replace("\n", " ").strip()
                findings.append(snippet)
        return list(dict.fromkeys(findings))  # Deduplicate preserving order

    def scan_for_compensation(self, page_content: str) -> List[str]:
        """Scans content for participant compensation (stipend, salary, cash prizes)."""
        findings: List[str] = []
        if not page_content:
            return findings
        for pattern in COMPENSATION_PATTERNS:
            for m in re.finditer(pattern, page_content, re.IGNORECASE):
                start = max(0, m.start() - 30)
                end = min(len(page_content), m.end() + 50)
                snippet = page_content[start:end].replace("\n", " ").strip()
                findings.append(snippet)
        return list(dict.fromkeys(findings))

    def is_trusted_official_domain(self, domain: str) -> bool:
        """Evaluates whether the source domain belongs to high-trust official or security registries."""
        if not domain:
            return False
        d_lower = domain.strip().lower()
        if any(d_lower.endswith(tld) for tld in HIGH_TRUST_TLDS):
            return True
        if d_lower in TRUSTED_SECURITY_DOMAINS or any(d_lower.endswith("." + td) for td in TRUSTED_SECURITY_DOMAINS):
            return True
        return False

