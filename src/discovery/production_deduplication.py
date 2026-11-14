"""
Layered Production Deduplication Engine for CyberScout AI (Phase F).

Implements deterministic multi-layer comparison between incoming staged candidates
and existing production Opportunities to prevent duplicate records and preserve
user bookmarks, first-seen timestamps, and notification state.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.logging import get_logger
from src.models.opportunity import Opportunity
from src.utils.url_utils import normalize_url

logger = get_logger(__name__)


class ProductionDeduplicator:
    """
    Multi-layer deduplication engine comparing canonical URLs, URL hashes,
    application URLs, identity fingerprints, and organization-scoped titles.
    """

    def __init__(self):
        pass

    @staticmethod
    def canonicalize_url(url: str) -> str:
        """
        Normalizes URL into a canonical string, removing tracking parameters,
        normalizing scheme and hostname, stripping fragments, and cleaning trailing slashes.
        """
        if not url or not isinstance(url, str):
            return ""
        return normalize_url(url.strip())

    @classmethod
    def compute_url_hash(cls, url: str) -> str:
        """Computes SHA-256 hash of the canonicalized URL."""
        canonical = cls.canonicalize_url(url)
        if not canonical:
            return ""
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def clean_text_core(text: Optional[str], max_len: int = 200) -> str:
        """Strips HTML tags, collapses whitespace, and lowercases text for fingerprinting."""
        if not text:
            return ""
        no_html = re.sub(r"<[^>]+>", " ", text)
        clean = " ".join(no_html.strip().lower().split())
        return clean[:max_len]

    @classmethod
    def compute_identity_fingerprint(
        cls,
        title: str,
        organization: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        source_id: str = "tavily",
    ) -> str:
        """
        Computes deterministic SHA-256 content fingerprint.
        Participating fields:
        - source_id (lowercased)
        - clean title
        - clean organization/provider
        - category (lowercased)
        - description core (first 200 chars)
        """
        clean_sid = (source_id or "tavily").strip().lower()
        clean_title = cls.clean_text_core(title, max_len=120)
        clean_org = cls.clean_text_core(organization, max_len=80)
        clean_cat = (category or "other").strip().lower()
        clean_desc = cls.clean_text_core(description, max_len=200)

        components = [clean_sid, clean_title, clean_org, clean_cat, clean_desc]
        canonical_str = "|".join(components)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @classmethod
    def are_titles_substantially_identical(cls, title_a: str, title_b: str) -> bool:
        """
        Determines whether two titles represent the exact same opportunity title
        after normalizing punctuation, year delimiters, and case.
        """
        t1 = cls.clean_text_core(title_a)
        t2 = cls.clean_text_core(title_b)
        if t1 == t2:
            return True

        # Remove non-alphanumeric chars (e.g. dashes, colons)
        t1_alnum = re.sub(r"[^a-z0-9]", "", t1)
        t2_alnum = re.sub(r"[^a-z0-9]", "", t2)
        if t1_alnum and t1_alnum == t2_alnum:
            return True

        return False

    def find_match(
        self,
        candidate_data: Dict[str, Any],
        existing_opportunities: List[Opportunity],
    ) -> Optional[Tuple[Opportunity, str]]:
        """
        Searches existing production opportunities for a matching record.

        Layered match order:
        1. Exact url_hash match
        2. Exact canonical URL match
        3. Exact application URL match against existing canonical/original URLs
        4. Exact identity fingerprint match
        5. Same organization AND substantially identical title

        Returns:
            Tuple of (matched_opportunity, match_reason) or None if genuinely new.
        """
        cand_url = candidate_data.get("canonical_url") or candidate_data.get("original_url") or ""
        cand_norm_url = self.canonicalize_url(cand_url)
        cand_url_hash = self.compute_url_hash(cand_norm_url)

        cand_app_url = candidate_data.get("application_url") or ""
        cand_app_norm = self.canonicalize_url(cand_app_url) if cand_app_url else ""

        cand_title = candidate_data.get("title") or ""
        cand_org = candidate_data.get("organization") or candidate_data.get("company") or candidate_data.get("provider") or ""
        cand_cat = candidate_data.get("category") or "other"
        cand_desc = candidate_data.get("description") or candidate_data.get("snippet") or ""

        cand_fp = self.compute_identity_fingerprint(
            title=cand_title,
            organization=cand_org,
            category=cand_cat,
            description=cand_desc,
        )

        for opp in existing_opportunities:
            opp_norm_url = self.canonicalize_url(opp.canonical_url or opp.url)
            opp_url_hash = opp.generate_url_hash() if hasattr(opp, "generate_url_hash") else self.compute_url_hash(opp_norm_url)

            # Layer 1: URL Hash Match
            if cand_url_hash and (cand_url_hash == opp_url_hash or cand_url_hash == getattr(opp, "url_hash", None)):
                return opp, "EXACT_URL_HASH_MATCH"

            # Layer 2: Canonical URL Match
            if cand_norm_url and opp_norm_url and cand_norm_url == opp_norm_url:
                return opp, "CANONICAL_URL_MATCH"

            # Layer 3: Application URL Match
            if cand_app_norm and (cand_app_norm == opp_norm_url or cand_app_norm == self.canonicalize_url(opp.url)):
                return opp, "APPLICATION_URL_MATCH"

            # Layer 4: Identity Fingerprint Match
            opp_fp = opp.identity_fingerprint or opp.compute_identity_fingerprint()
            if cand_fp and opp_fp and cand_fp == opp_fp:
                return opp, "IDENTITY_FINGERPRINT_MATCH"

            # Layer 5: Organization + Substantially Identical Title
            opp_org = opp.company or opp.provider or ""
            if cand_org and opp_org:
                clean_cand_org = self.clean_text_core(cand_org)
                clean_opp_org = self.clean_text_core(opp_org)
                if clean_cand_org == clean_opp_org:
                    if self.are_titles_substantially_identical(cand_title, opp.title):
                        # Verify categories do not contradict (e.g. Job vs CTF at same company)
                        cand_cat_norm = (cand_cat or "").strip().lower()
                        opp_cat_norm = (opp.category or "").strip().lower()
                        if cand_cat_norm == opp_cat_norm or cand_cat_norm == "other" or opp_cat_norm == "other":
                            return opp, "ORG_AND_TITLE_MATCH"

        return None

    @classmethod
    def detect_meaningful_changes(
        cls,
        candidate_data: Dict[str, Any],
        existing_opp: Opportunity,
    ) -> List[str]:
        """
        Detects whether an incoming candidate contains meaningful updates compared
        to an existing production opportunity.

        Monitored fields:
        - deadline (newly announced or updated)
        - description (enriched content)
        - requirements / eligibility
        - remote status
        - application_url
        """
        changes: List[str] = []

        cand_dl = str(candidate_data.get("deadline") or "").strip()
        opp_dl = str(existing_opp.deadline or "").strip()
        if cand_dl and cand_dl != opp_dl:
            changes.append("deadline")

        cand_desc = (candidate_data.get("description") or "").strip()
        opp_desc = (existing_opp.description or "").strip()
        if len(cand_desc) > (len(opp_desc) + 50): # Richer content
            changes.append("description")

        cand_req = (candidate_data.get("requirements") or candidate_data.get("required_skills") or "").strip()
        opp_req = (existing_opp.requirements or "").strip()
        if cand_req and cand_req != opp_req and len(cand_req) > len(opp_req):
            changes.append("requirements")

        cand_remote = candidate_data.get("remote")
        if cand_remote is not None and bool(cand_remote) != bool(existing_opp.remote):
            changes.append("remote")

        cand_app_url = (candidate_data.get("application_url") or "").strip()
        if cand_app_url:
            norm_cand_app = cls.canonicalize_url(cand_app_url)
            norm_opp_app = cls.canonicalize_url(existing_opp.canonical_url or existing_opp.url)
            if norm_cand_app and norm_opp_app and norm_cand_app != norm_opp_app:
                changes.append("application_url")

        return changes
