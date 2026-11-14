"""
Firecrawl Content Extraction Service for CyberScout AI.

Orchestrates deep content extraction for staged opportunity candidate URLs
discovered by Tavily. Validates remote URLs against SSRF/rebinding,
invokes Firecrawl with JavaScript rendering, normalizes opportunity fields,
detects duplicate page content, and updates staging in DiscoveredCandidates.

Does NOT promote unverified candidates to production Opportunities.
"""

from datetime import datetime, timezone
import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Set
import urllib.parse
import uuid

from src.core.logging import get_logger
from src.database.connection import DatabaseManager
from src.discovery.candidate_repository import DiscoveredCandidateRepository
from src.discovery.client_firecrawl import (
    FirecrawlAPIError,
    FirecrawlAuthError,
    FirecrawlBudgetExceededError,
    FirecrawlClient,
    FirecrawlRateLimitError,
    FirecrawlSecurityError,
    FirecrawlTimeoutError,
    sanitize_firecrawl_secret,
)
from src.discovery.discovery_models import (
    CandidateProcessingStatus,
    DiscoveredCandidate,
    ExtractedContentData,
    ExtractionBudget,
    ExtractionRunSummary,
    ExtractionStatus,
)
from src.discovery.url_validator import URLValidator

logger = get_logger(__name__)

# Heuristic patterns for extracting evidence from page content without hallucination
DEADLINE_PATTERNS = [
    r"(?:deadline|apply\s+by|last\s+date|due\s+date|closing\s+date|ends\s+on)[:\s]+([A-Za-z0-9\s,\/\.\-]+(?:202\d|203\d))",
    r"(\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+202\d\b)",
]

FEE_EVIDENCE_PATTERNS = [
    r"([^.\n]*?(?:free\s+of\s+cost|100%\s+free|no\s+fee|free\s+registration|completely\s+free|free\s+admission|free\s+to\s+apply)[^.\n]*)",
    r"([^.\n]*?(?:registration\s+fee|application\s+fee|tuition|participation\s+fee|entry\s+fee|cost|pricing|price|fee)[^.\n]*?(?:\$|₹|€|£|usd|inr|eur)\s*\d+[^.\n]*)",
    r"([^.\n]*?(?:\$|₹|€|£|usd|inr|eur)\s*\d+[^.\n]*?(?:registration|fee|tuition|cost|price|ticket)[^.\n]*)",
]

CURRENCY_AMOUNT_PATTERN = r"(?:\$|₹|€|£|USD|INR|EUR|GBP)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)"

REMOTE_PATTERNS = [
    r"\b(remote|work\s+from\s+home|wfh|virtual|anywhere|worldwide)\b",
    r"\b(hybrid|flexible\s+location)\b",
    r"\b(onsite|in-person|on-premise|office\s+only)\b",
]

SKILL_PATTERNS = [
    r"\b(python|golang|go|rust|bash|c\+\+|java|javascript|typescript)\b",
    r"\b(siem|soc|splunk|qradar|sentinel|wireshark|tcpdump|snort|suricata)\b",
    r"\b(pentesting|penetration\s+testing|burp\s+suite|metasploit|nmap|owasp)\b",
    r"\b(malware\s+analysis|reverse\s+engineering|ghidra|ida\s+pro|x64dbg)\b",
    r"\b(threat\s+intelligence|osint|threat\s+hunting|mitre\s+att&ck|dfir|forensics)\b",
    r"\b(cloud\s+security|aws\s+security|azure\s+security|gcp\s+security|kubernetes\s+security)\b",
    r"\b(cryptography|web3\s+security|smart\s+contract\s+audit|api\s+security)\b",
]


class FirecrawlExtractionService:
    """
    Master content extraction service orchestrating Firecrawl web scraping
    for staged candidate URLs discovered by Tavily.
    """

    def __init__(
        self,
        firecrawl_client: Optional[FirecrawlClient] = None,
        url_validator: Optional[URLValidator] = None,
        candidate_repo: Optional[DiscoveredCandidateRepository] = None,
        db_manager: Optional[DatabaseManager] = None,
        budget: Optional[ExtractionBudget] = None,
    ):
        self.db_manager = db_manager or DatabaseManager()
        self.budget = budget or ExtractionBudget()
        self.firecrawl_client = firecrawl_client or FirecrawlClient(budget=self.budget)
        # SSRF Security Validator with live DNS resolution enabled for extraction
        self.url_validator = url_validator or URLValidator(resolve_dns=True)
        self.candidate_repo = candidate_repo or DiscoveredCandidateRepository(db_manager=self.db_manager)

    def extract_fields_from_evidence(
        self,
        original_url: str,
        canonical_url: str,
        raw_scrape_data: Dict[str, Any],
        candidate_category: Optional[str] = None,
    ) -> ExtractedContentData:
        """
        Parses Firecrawl scrape response into structured opportunity fields.
        Derives all fields strictly from source evidence without hallucination.
        """
        markdown = raw_scrape_data.get("markdown") or ""
        html = raw_scrape_data.get("html") or ""
        meta = raw_scrape_data.get("metadata") or {}

        # 1. Content Hash (for cross-URL duplicate page detection)
        content_hash = hashlib.sha256(markdown.encode("utf-8", errors="ignore")).hexdigest() if markdown else ""

        # 2. Page Title
        title = meta.get("title") or meta.get("ogTitle")
        if not title and markdown:
            # First markdown heading # ...
            heading_match = re.search(r"^#\s+([^\n]+)", markdown, re.MULTILINE)
            if heading_match:
                title = heading_match.group(1).strip()

        # 3. Organization or Publisher
        org = meta.get("ogSiteName") or meta.get("author") or meta.get("publisher")
        if not org:
            # Fallback to source domain
            parsed_domain = urllib.parse.urlparse(canonical_url).hostname or ""
            if parsed_domain:
                clean_host = parsed_domain.replace("www.", "")
                org = clean_host.split(".")[0].capitalize()

        # 4. Short Description
        desc = meta.get("description") or meta.get("ogDescription")
        if not desc and markdown:
            # Clean first non-heading paragraph
            paragraphs = [p.strip() for p in markdown.split("\n\n") if p.strip() and not p.strip().startswith("#")]
            if paragraphs:
                desc = paragraphs[0][:300].strip()

        # 5. Remote vs Onsite Status
        combined_text = f"{title or ''}\n{desc or ''}\n{markdown[:4000]}".lower()
        remote_status = None
        if "remote" in combined_text or "work from home" in combined_text or "virtual" in combined_text:
            remote_status = "remote"
        elif "hybrid" in combined_text:
            remote_status = "hybrid"
        elif "onsite" in combined_text or "in-person" in combined_text or "on-site" in combined_text:
            remote_status = "onsite"

        # 6. Required Skills
        matched_skills: Set[str] = set()
        for pattern in SKILL_PATTERNS:
            for match in re.finditer(pattern, combined_text, re.IGNORECASE):
                matched_skills.add(match.group(1).lower().strip())
        skills_list = sorted(list(matched_skills))

        # 7. Application Deadline
        deadline = None
        for pattern in DEADLINE_PATTERNS:
            m = re.search(pattern, markdown[:8000], re.IGNORECASE)
            if m:
                deadline = m.group(1).strip()
                break

        # 8. Publication Date
        pub_date = (
            meta.get("articlePublishedTime")
            or meta.get("publishedTime")
            or meta.get("date")
        )
        if pub_date:
            pub_date = str(pub_date).strip()

        # 9. Application URL
        app_url = canonical_url
        apply_match = re.search(r'\[(?:Apply\s+Now|Apply|Register|Enroll|Submit\s+Application)\]\((https?://[^\s\)]+)\)', markdown, re.IGNORECASE)
        if apply_match:
            app_url = apply_match.group(1).strip()

        # 10. Pricing & Fee Evidence
        fee_statements: List[str] = []
        for pattern in FEE_EVIDENCE_PATTERNS:
            for m in re.finditer(pattern, markdown[:10000], re.IGNORECASE):
                cleaned_sentence = re.sub(r"\s+", " ", m.group(1)).strip()
                if cleaned_sentence and cleaned_sentence not in fee_statements:
                    fee_statements.append(cleaned_sentence[:200])

        pricing_text = "; ".join(fee_statements) if fee_statements else None

        # Parse explicit fee and currency if present
        currency = None
        fee_amount = None
        if pricing_text:
            amt_match = re.search(CURRENCY_AMOUNT_PATTERN, pricing_text)
            if amt_match:
                raw_amt = amt_match.group(1).replace(",", "")
                try:
                    fee_amount = float(raw_amt)
                    if "$" in amt_match.group(0) or "USD" in amt_match.group(0).upper():
                        currency = "USD"
                    elif "₹" in amt_match.group(0) or "INR" in amt_match.group(0).upper():
                        currency = "INR"
                    elif "€" in amt_match.group(0) or "EUR" in amt_match.group(0).upper():
                        currency = "EUR"
                    elif "£" in amt_match.group(0) or "GBP" in amt_match.group(0).upper():
                        currency = "GBP"
                except ValueError:
                    pass

        # 11. Source Evidence Quotations
        source_evidence: List[str] = []
        if pricing_text:
            source_evidence.extend(fee_statements[:3])
        if deadline:
            source_evidence.append(f"Deadline statement: {deadline}")
        if remote_status:
            source_evidence.append(f"Work arrangement detected: {remote_status}")

        return ExtractedContentData(
            original_url=original_url,
            canonical_url=canonical_url,
            title=title,
            organization_or_publisher=org,
            main_content_markdown=markdown,
            main_content_html=html[:50000] if html else None,  # Cap raw HTML for storage efficiency
            short_description=desc,
            opportunity_type=candidate_category or "other",
            required_skills=skills_list,
            eligibility_requirements=None,  # Preserved null until Phase D AI classifier evaluates
            country_and_location=None,
            remote_or_onsite=remote_status,
            publication_date=pub_date,
            application_deadline=deadline,
            application_url=app_url,
            pricing_statements=pricing_text,
            currency=currency,
            fee_amount=fee_amount,
            source_evidence=source_evidence,
            content_hash=content_hash,
            raw_metadata=meta,
        )

    def run_extraction(
        self,
        candidates: Optional[List[DiscoveredCandidate]] = None,
        max_pages: Optional[int] = None,
        run_id: Optional[str] = None,
        dry_run: bool = False,
        progress_callback: Optional[Any] = None,
    ) -> ExtractionRunSummary:
        """
        Executes Firecrawl extraction cycle across staged candidates.

        1. Selects pending candidates awaiting extraction.
        2. Strictly validates target URLs with live DNS against SSRF/rebinding.
        3. Submits URLs to Firecrawl Scrape API.
        4. Validates returned canonical redirects against SSRF.
        5. Extracts structured opportunity fields derived strictly from page evidence.
        6. Detects and flags duplicate page content.
        7. Updates candidate records in DiscoveredCandidates staging table.
        8. Returns ExtractionRunSummary.
        """
        start_time = time.time()
        active_run_id = run_id or f"extract-{uuid.uuid4()}"
        started_iso = datetime.now(timezone.utc).isoformat()

        logger.info("================================================================")
        logger.info(f"[ExtractionService] Starting Firecrawl Content Extraction Run: {active_run_id}")
        logger.info("================================================================")

        summary = ExtractionRunSummary(
            run_id=active_run_id,
            started_at=started_iso,
        )

        def _notify(pct: float, msg: str):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        # Check configuration
        if not self.firecrawl_client.is_enabled:
            logger.info("[ExtractionService] Firecrawl extraction is disabled by configuration. Skipping.")
            summary.status = "disabled"
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        if not self.firecrawl_client.is_configured and not dry_run:
            msg = "FIRECRAWL_API_KEY is missing or invalid. Extraction cannot proceed."
            logger.warning(f"[ExtractionService] {msg}")
            summary.status = "skipped_missing_credentials"
            summary.errors.append(msg)
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        # 1. Fetch Candidates
        effective_max = min(max_pages or self.budget.max_pages_per_run, self.budget.max_pages_per_run)
        if candidates is not None:
            target_candidates = candidates[:effective_max]
        else:
            target_candidates = self.candidate_repo.get_candidates_for_extraction(limit=effective_max)

        summary.pages_attempted = len(target_candidates)
        logger.info(f"[ExtractionService] Selected {len(target_candidates)} staged candidates for Firecrawl extraction.")

        if not target_candidates:
            summary.status = "completed"
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.duration_seconds = round(time.time() - start_time, 2)
            return summary

        seen_content_hashes: Set[str] = set()
        total_pages = len(target_candidates)

        for idx, candidate in enumerate(target_candidates):
            step_pct = 10.0 + ((idx / total_pages) * 80.0)
            _notify(step_pct, f"Scraping ({idx + 1}/{total_pages}): {candidate.source_domain or candidate.canonical_url}")

            target_url = candidate.canonical_url or candidate.original_url

            # 2. SSRF Security Pre-Check (Local live DNS resolution check)
            val_result = self.url_validator.validate(target_url)
            if not val_result.is_valid:
                rej_reason = val_result.rejection_reason or "SSRF/Dangerous target URL rejected"
                logger.warning(f"[ExtractionService] SSRF Security Rejected URL '{target_url}': {rej_reason}")
                summary.pages_rejected_security += 1
                summary.pages_failed += 1

                if not dry_run:
                    self.candidate_repo.update_candidate_extraction(
                        candidate_id=candidate.id,
                        extraction_status=ExtractionStatus.SKIPPED.value,
                        processing_status=CandidateProcessingStatus.SECURITY_REJECTED.value,
                        metadata_updates={"security_rejection": rej_reason},
                    )
                continue

            # 3. Firecrawl Scrape Execution
            try:
                scrape_data = self.firecrawl_client.scrape_url(
                    url=target_url,
                    formats=["markdown", "html"],
                    only_main_content=True,
                )
            except (FirecrawlAuthError, FirecrawlBudgetExceededError) as critical_err:
                logger.error(f"[ExtractionService] Critical Firecrawl error on '{target_url}': {critical_err}")
                summary.errors.append(str(critical_err))
                summary.status = "stopped_on_budget_or_auth"
                summary.pages_failed += 1
                break
            except (FirecrawlRateLimitError, FirecrawlTimeoutError, FirecrawlAPIError) as scrape_err:
                logger.warning(f"[ExtractionService] Scrape failed for '{target_url}': {scrape_err}")
                summary.pages_failed += 1
                summary.errors.append(sanitize_firecrawl_secret(str(scrape_err)))

                # Keep candidate in DiscoveredCandidates with 'failed' status for controlled retry
                if not dry_run:
                    self.candidate_repo.update_candidate_extraction(
                        candidate_id=candidate.id,
                        extraction_status=ExtractionStatus.FAILED.value,
                        metadata_updates={"last_extraction_error": str(scrape_err)},
                    )
                continue
            except Exception as unexp_err:
                logger.error(f"[ExtractionService] Unexpected scrape failure: {unexp_err}", exc_info=True)
                summary.pages_failed += 1
                summary.errors.append(sanitize_firecrawl_secret(str(unexp_err)))
                if not dry_run:
                    self.candidate_repo.update_candidate_extraction(
                        candidate_id=candidate.id,
                        extraction_status=ExtractionStatus.FAILED.value,
                        metadata_updates={"last_extraction_error": str(unexp_err)},
                    )
                continue

            # 4. Post-Fetch Canonical & SSRF Check on returned redirect destination
            meta = scrape_data.get("metadata") or {}
            returned_canonical = meta.get("sourceURL") or meta.get("canonicalURL") or target_url
            if returned_canonical != target_url:
                redirect_val = self.url_validator.validate(returned_canonical)
                if not redirect_val.is_valid:
                    rej_reason = f"Redirected to prohibited destination: {redirect_val.rejection_reason}"
                    logger.warning(f"[ExtractionService] {rej_reason}")
                    summary.pages_rejected_security += 1
                    summary.pages_failed += 1
                    if not dry_run:
                        self.candidate_repo.update_candidate_extraction(
                            candidate_id=candidate.id,
                            extraction_status=ExtractionStatus.SKIPPED.value,
                            processing_status=CandidateProcessingStatus.SECURITY_REJECTED.value,
                            metadata_updates={"security_rejection": rej_reason},
                        )
                    continue

            # 5. Content Quality Check
            markdown_content = scrape_data.get("markdown") or ""
            if not markdown_content.strip() or len(markdown_content.strip()) < 30:
                err_msg = "Firecrawl returned empty or low-quality content (<30 characters)."
                logger.info(f"[ExtractionService] Low quality page for '{target_url}': {err_msg}")
                summary.pages_failed += 1
                if not dry_run:
                    self.candidate_repo.update_candidate_extraction(
                        candidate_id=candidate.id,
                        extraction_status=ExtractionStatus.FAILED.value,
                        metadata_updates={"last_extraction_error": err_msg},
                    )
                continue

            # 6. Extract Structured Opportunity Fields (Zero Hallucination)
            extracted = self.extract_fields_from_evidence(
                original_url=candidate.original_url,
                canonical_url=returned_canonical,
                raw_scrape_data=scrape_data,
                candidate_category=candidate.category,
            )

            # 7. Duplicate Content Check
            if extracted.content_hash and extracted.content_hash in seen_content_hashes:
                logger.info(f"[ExtractionService] Duplicate page content detected for '{target_url}'.")
                summary.pages_duplicate += 1
                if not dry_run:
                    self.candidate_repo.update_candidate_extraction(
                        candidate_id=candidate.id,
                        extraction_status=ExtractionStatus.SKIPPED.value,
                        processing_status=CandidateProcessingStatus.DUPLICATE.value,
                        canonical_url=returned_canonical,
                        metadata_updates={
                            "content_hash": extracted.content_hash,
                            "duplicate_content": True,
                        },
                    )
                continue

            if extracted.content_hash:
                seen_content_hashes.add(extracted.content_hash)

            # 8. Persist Extracted Data to Candidate Staging
            summary.pages_succeeded += 1
            if not dry_run:
                self.candidate_repo.update_candidate_extraction(
                    candidate_id=candidate.id,
                    extraction_status=ExtractionStatus.COMPLETED.value,
                    processing_status=CandidateProcessingStatus.READY_FOR_EXTRACTION.value,
                    canonical_url=returned_canonical,
                    title=extracted.title or candidate.title,
                    snippet=extracted.short_description or candidate.snippet,
                    metadata_updates={"extraction": extracted.to_dict()},
                )

        _notify(100.0, "Content Extraction Completed")
        finished_time = time.time()
        summary.completed_at = datetime.now(timezone.utc).isoformat()
        summary.duration_seconds = round(finished_time - start_time, 2)
        if summary.status not in ("stopped_on_budget_or_auth", "disabled", "skipped_missing_credentials"):
            summary.status = "completed" if summary.pages_failed == 0 else "partial"

        logger.info(
            f"[ExtractionService] Extraction finished in {summary.duration_seconds}s | "
            f"Attempted: {summary.pages_attempted} | Succeeded: {summary.pages_succeeded} | "
            f"Failed: {summary.pages_failed} | Security Rejected: {summary.pages_rejected_security} | "
            f"Duplicates: {summary.pages_duplicate}"
        )
        return summary
