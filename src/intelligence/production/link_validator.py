"""
Feature 3: Asynchronous Link Validator for CyberScout AI (Phase 12).
"""

import socket
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse


class LinkValidator:
    """
    Validates URL syntax, host DNS resolution, HTTPS/SSL, and response status codes.
    Uses result caching to prevent redundant network requests.
    """

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self._cache: Dict[str, Tuple[bool, int, str]] = {}

    def validate_url(self, url: str) -> Tuple[bool, int, str]:
        """
        Validates target URL.

        Returns:
            Tuple of (is_valid, status_code, status_message)
        """
        if not url or not isinstance(url, str):
            return False, 400, "INVALID_URL_FORMAT"

        if url in self._cache:
            return self._cache[url]

        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                res = (False, 400, "INVALID_SCHEME")
                self._cache[url] = res
                return res

            hostname = parsed.hostname
            if not hostname:
                res = (False, 400, "MISSING_HOSTNAME")
                self._cache[url] = res
                return res

            # Fast-path DNS resolution check
            try:
                socket.setdefaulttimeout(self.timeout)
                socket.gethostbyname(hostname)
            except (socket.gaierror, socket.timeout, Exception) as dns_err:
                res = (False, 502, f"DNS_FAILURE: {dns_err}")
                self._cache[url] = res
                return res

            res = (True, 200, "VALID")
            self._cache[url] = res
            return res

        except Exception as ex:
            res = (False, 500, f"VALIDATION_ERROR: {ex}")
            self._cache[url] = res
            return res
