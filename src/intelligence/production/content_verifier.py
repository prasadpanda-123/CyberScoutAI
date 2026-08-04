"""
Feature 4: Page Content Verifier for CyberScout AI (Phase 12).
"""

from typing import List, Optional, Tuple


class ContentVerifier:
    """
    Verifies ingested page text & HTML content to reject login walls, CAPTCHAs, parking domains,
    spam redirects, and empty pages.
    """

    SUSPICIOUS_CONTENT_PATTERNS: List[str] = [
        "please log in to continue",
        "login to access",
        "sign in to continue",
        "verify you are human",
        "cloudflare ray id",
        "enable javascript to continue",
        "domain for sale",
        "this domain is parked",
        "buy this domain",
        "404 not found",
        "403 forbidden",
        "access denied",
        "page not found",
    ]

    def verify_content(
        self,
        title: str,
        description: Optional[str] = None,
        raw_text: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Verifies content payload.

        Returns:
            Tuple of (is_verified, verification_status_message)
        """
        combined = f"{title or ''} {description or ''} {raw_text or ''}".lower()

        if not combined.strip() or len(combined.strip()) < 10:
            return False, "EMPTY_PAGE_CONTENT"

        for pat in self.SUSPICIOUS_CONTENT_PATTERNS:
            if pat in combined:
                if "login" in pat or "log in" in pat or "sign in" in pat:
                    return False, "LOGIN_GATE_DETECTED"
                elif "human" in pat or "cloudflare" in pat or "javascript" in pat:
                    return False, "CAPTCHA_OR_BOT_GATE"
                elif "domain" in pat:
                    return False, "PARKED_DOMAIN"
                elif "404" in pat or "not found" in pat or "forbidden" in pat:
                    return False, "DEAD_PAGE_OR_404"

        return True, "VERIFIED"
