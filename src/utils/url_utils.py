"""
URL Normalization and Sanitization Utility for CyberScout AI.

Provides robust URL validation, hostname sanitization, protocol checking,
and DNS-safe domain normalization to prevent runtime socket resolution errors.
"""

import re
import urllib.parse
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)

# Known domain overrides for legacy or malformed identifiers
OFFICIAL_DOMAIN_MAP = {
    "portswigger_academy.com": "portswigger.net",
    "portswigger_academy": "portswigger.net",
    "tryhackme.com": "tryhackme.com",
    "hackthebox.com": "academy.hackthebox.com",
    "cisco_netacad": "netacad.com",
}


def sanitize_url(url: str, default_scheme: str = "https") -> str:
    """
    Sanitizes, normalizes, and validates URL strings to ensure DNS & HTTP safety.

    Args:
        url: Raw input URL string.
        default_scheme: Default protocol scheme if missing (defaults to 'https').

    Returns:
        Sanitized and normalized URL string.

    Raises:
        ValueError: If URL is unparseable or violates security boundaries.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL string must be a non-empty string.")

    cleaned = url.strip()

    # Reject unsupported or dangerous protocol schemes
    lower_cleaned = cleaned.lower()
    for forbidden in ["file://", "ftp://", "javascript:", "data:", "vbscript:"]:
        if lower_cleaned.startswith(forbidden):
            raise ValueError(f"Forbidden protocol scheme in URL: '{url}'")

    # Add default scheme if missing
    if not re.match(r"^https?://", cleaned, re.IGNORECASE):
        cleaned = f"{default_scheme}://{cleaned}"

    try:
        parsed = urllib.parse.urlparse(cleaned)
    except Exception as e:
        raise ValueError(f"Malformed URL string '{url}': {e}")

    scheme = parsed.scheme.lower()
    if scheme not in ["http", "https"]:
        raise ValueError(f"Unsupported protocol scheme '{scheme}' in URL.")

    netloc = parsed.netloc.strip()
    if not netloc:
        raise ValueError(f"Missing hostname in URL '{url}'.")

    # Check for userinfo (username:password@hostname)
    userinfo = ""
    hostname = netloc
    if "@" in netloc:
        userinfo, hostname = netloc.rsplit("@", 1)

    # Extract host and port
    port_str = ""
    if ":" in hostname:
        host_parts = hostname.split(":")
        hostname = host_parts[0]
        if len(host_parts) > 1:
            port_str = f":{host_parts[1]}"

    # Reject localhost or internal loopback IP addresses for external collectors
    lower_host = hostname.lower()
    if lower_host in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
        raise ValueError(f"Localhost and internal loopback addresses prohibited: '{url}'")

    # Apply official domain mapping override if present
    if lower_host in OFFICIAL_DOMAIN_MAP:
        hostname = OFFICIAL_DOMAIN_MAP[lower_host]
    elif "_" in hostname:
        # Underscores in hostnames violate DNS rules (RFC 1035) causing socket.gaierror
        logger.warning(f"Sanitizing DNS-invalid hostname containing underscore: '{hostname}'")
        hostname = hostname.replace("_", "-")

    # Reconstruct clean path without duplicate slashes
    path = parsed.path
    if path:
        # Remove consecutive slashes while preserving leading slash
        path = re.sub(r"/{2,}", "/", path)

    # Reconstruct query string
    query = parsed.query

    # Reassemble sanitized URL
    reconstructed_netloc = f"{userinfo}@{hostname}" if userinfo else hostname
    reconstructed_netloc += port_str

    sanitized = urllib.parse.urlunparse((
        scheme,
        reconstructed_netloc,
        path,
        parsed.params,
        query,
        parsed.fragment,
    ))

    return sanitized


def is_valid_url(url: str) -> bool:
    """
    Checks if a URL string is valid and safely parseable.

    Args:
        url: Input URL string.

    Returns:
        True if URL is valid, False otherwise.
    """
    try:
        sanitize_url(url)
        return True
    except (ValueError, Exception):
        return False


TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_name", "utm_cid", "utm_reader", "fbclid", "gclid", "msclkid",
    "_ga", "_ke", "mc_cid", "mc_eid", "ref", "ref_src", "source", "feature",
    "trk", "igshid", "ncid"
}


def normalize_url(url: str) -> str:
    """
    Normalizes a URL into a canonical string representation for accurate deduplication.
    Rules:
    - Normalizes protocol scheme to lowercase https (treating http and https as equivalent web protocols).
    - Lowercases hostname and strips 'www.' prefix for canonical domain matching.
    - Strips default ports (:80 for http, :443 for https).
    - Removes trailing slashes on paths (/ctf/ -> /ctf) while preserving root (/).
    - Removes URL fragments (#section, #overview).
    - Strips tracking & campaign query parameters while preserving resource parameters (?id=123, ?page=2).
    - Safely unquotes unnecessary URL percent-encodings and sorts query parameters deterministically.
    """
    if not url or not isinstance(url, str):
        return ""

    cleaned = url.strip()
    if not cleaned:
        return ""

    if not re.match(r"^https?://", cleaned, re.IGNORECASE):
        cleaned = f"https://{cleaned}"

    try:
        parsed = urllib.parse.urlparse(cleaned)
    except Exception:
        return cleaned.lower().rstrip("/")

    scheme = parsed.scheme.lower()
    if scheme in ("http", "https"):
        scheme = "https"

    netloc = parsed.netloc.lower()

    # Strip default ports
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif netloc.endswith(":443"):
        netloc = netloc[:-4]

    # Strip userinfo if present
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]

    # Strip www. prefix for canonical host matching
    host = netloc
    if host.startswith("www."):
        host = host[4:]

    # Apply official domain mapping if present
    if host in OFFICIAL_DOMAIN_MAP:
        host = OFFICIAL_DOMAIN_MAP[host]

    # Clean path (strip trailing slash for non-root paths)
    path = urllib.parse.unquote(parsed.path)
    if path and path != "/":
        path = path.rstrip("/")

    # Strip tracking parameters from query string
    query_params = []
    if parsed.query:
        for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() not in TRACKING_PARAMS:
                query_params.append((key, val))

    query_str = urllib.parse.urlencode(sorted(query_params)) if query_params else ""

    # Reconstruct canonical URL (ignoring fragment)
    canonical = urllib.parse.urlunparse((
        scheme,
        host,
        path or "/",
        "",
        query_str,
        ""  # Fragment stripped
    ))

    return canonical


def is_safe_internal_url(target: Optional[str]) -> bool:
    """
    Verifies that a redirect target is strictly a safe, internal, relative path.
    Defends against Open Redirect attacks (SEC-01):
    - Rejects absolute URLs (http://, https://, ftp://, etc.)
    - Rejects protocol-relative URLs (//attacker.example, ///)
    - Rejects backslash obfuscation (\\attacker, /\\attacker, /%5c, /%255c)
    - Rejects scheme-relative URLs (javascript:, data:, vbscript:, blob:, etc.)
    - Rejects encoded slash/backslash variants (/%2f, /%5c, /%252f, /%255c)
    - Rejects control characters, null bytes, and CRLF (header injection)
    """
    if not target or not isinstance(target, str):
        return False

    target = target.strip()
    if not target:
        return False

    # Prevent control characters, CRLF, tabs, null bytes (header injection & parsing evasions)
    if any(ord(c) < 32 or ord(c) == 127 for c in target):
        return False

    # Must start with a single slash, not protocol-relative //, ///, or backslash \
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return False

    # Multi-pass unquote to neutralize nested/double-encoded bypasses (e.g. %252f, %255c)
    curr = target
    for _ in range(3):
        try:
            nxt = urllib.parse.unquote(curr)
        except Exception:
            return False
        if nxt == curr:
            break
        curr = nxt
    unquoted = curr

    if not unquoted.startswith("/") or unquoted.startswith("//") or "\\" in unquoted:
        return False

    # Disallow control characters or whitespace/spaces in unquoted string (e.g. /admin%20/dashboard)
    if any(ord(c) <= 32 or ord(c) == 127 for c in unquoted):
        return False

    # Check dangerous schemes / pseudo-protocols anywhere in unquoted string
    lower_unquoted = unquoted.lower()
    for bad in ("javascript:", "data:", "vbscript:", "http:", "https:", "ftp:", "file:", "blob:", "about:"):
        if bad in lower_unquoted:
            return False

    try:
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or parsed.netloc:
            return False
        if not parsed.path.startswith("/") or parsed.path.startswith("//"):
            return False

        # Also parse unquoted target
        parsed_unquoted = urllib.parse.urlsplit(unquoted)
        if parsed_unquoted.scheme or parsed_unquoted.netloc:
            return False
        if not parsed_unquoted.path.startswith("/") or parsed_unquoted.path.startswith("//"):
            return False
    except Exception:
        return False

    return True

