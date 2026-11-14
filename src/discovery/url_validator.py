"""
Authoritative URL Security and SSRF Defense Validator for CyberScout AI.

Strictly filters untrusted discovered URLs to prevent:
- Server-Side Request Forgery (SSRF)
- DNS Rebinding Attacks
- Cloud Metadata Access (AWS/GCP/Azure/DigitalOcean 169.254.169.254)
- Internal / Private / Loopback IP Access (RFC 1918, RFC 3927)
- Dangerous pseudo-protocols (file://, javascript:, data:, blob:)
- Malformed URLs and credential injection
"""

from dataclasses import dataclass
import hashlib
import ipaddress
import re
import socket
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse

from src.core.logging import get_logger
from src.utils.url_utils import normalize_url

logger = get_logger(__name__)

# Strict prohibited IP networks (IPv4 and IPv6)
PROHIBITED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918 Private
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space / Carrier Grade NAT
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918 Private
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1 documentation
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2 documentation
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3 documentation
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6 Networks
    ipaddress.ip_network("::1/128"),            # IPv6 Loopback
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local Unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
]

# Explicit prohibited hostnames (case-insensitive)
PROHIBITED_HOSTNAMES: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "local",
    "internal",
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
    "169.254.170.2",
    "aws-metadata",
    "gcp-metadata",
    "azure-metadata",
}

# Dangerous pseudo-protocols strictly rejected
FORBIDDEN_PROTOCOLS = {"file:", "javascript:", "data:", "vbscript:", "blob:", "gopher:", "dict:", "ldap:", "tftp:"}

# File extensions that represent binaries, executables, or non-web media
PROHIBITED_EXTENSIONS = {
    ".exe", ".bin", ".dmg", ".pkg", ".sh", ".bat", ".cmd", ".msi", ".iso",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".dll", ".so", ".apk",
}


@dataclass
class URLValidationResult:
    """Result of defensive URL inspection and validation."""

    is_valid: bool
    original_url: str
    canonical_url: str = ""
    url_hash: str = ""
    domain: str = ""
    rejection_reason: Optional[str] = None


class URLValidator:
    """
    Security gate inspecting candidate URLs before processing or content extraction.
    """

    def __init__(self, resolve_dns: bool = False, dns_timeout: float = 2.0):
        """
        Args:
            resolve_dns: If True, executes live DNS resolution to defend against rebinding.
                         Defaults to False for fast non-blocking discovery, enabled on extraction.
            dns_timeout: Timeout in seconds for socket DNS resolution.
        """
        self.resolve_dns = resolve_dns
        self.dns_timeout = dns_timeout

    @staticmethod
    def _parse_ip_safely(host: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """Safely parses IPv4 or IPv6 string, including numeric/decimal formats."""
        clean_host = host.strip("[]")
        try:
            return ipaddress.ip_address(clean_host)
        except ValueError:
            # Check integer or octal representation of IPv4 (e.g. 2130706433 or 0177.0.0.1)
            if re.match(r"^\d+$", clean_host):
                try:
                    return ipaddress.IPv4Address(int(clean_host))
                except (ValueError, OverflowError):
                    pass
            return None

    @classmethod
    def is_ip_prohibited(cls, ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> Tuple[bool, str]:
        """
        Checks whether an IP address belongs to loopback, private, link-local,
        carrier-grade NAT, or metadata networks.
        """
        # Unpack IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1)
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
            ip_obj = ip_obj.ipv4_mapped

        for net in PROHIBITED_NETWORKS:
            if ip_obj in net:
                return True, f"Prohibited IP network: {net}"

        if ip_obj.is_loopback:
            return True, "Loopback address is prohibited"
        if ip_obj.is_private:
            return True, "Private / internal RFC 1918 address is prohibited"
        if ip_obj.is_link_local:
            return True, "Link-local address is prohibited"
        if ip_obj.is_multicast:
            return True, "Multicast address is prohibited"
        if ip_obj.is_reserved:
            return True, "Reserved address is prohibited"
        if not ip_obj.is_global:
            return True, "Non-public address is prohibited"

        return False, ""

    def validate(self, url: str) -> URLValidationResult:
        """
        Validates a URL against SSRF, dangerous protocols, IP boundaries, and malformed structures.

        Returns:
            URLValidationResult indicating pass/fail status and canonical information.
        """
        if not url or not isinstance(url, str):
            return URLValidationResult(
                is_valid=False,
                original_url=str(url),
                rejection_reason="URL is empty or not a string",
            )

        clean_url = url.strip()
        lower_url = clean_url.lower()

        # 1. Reject dangerous pseudo-protocols
        for bad_proto in FORBIDDEN_PROTOCOLS:
            if lower_url.startswith(bad_proto):
                return URLValidationResult(
                    is_valid=False,
                    original_url=clean_url,
                    rejection_reason=f"Forbidden protocol scheme: {bad_proto}",
                )

        # 2. Reject control characters, newlines, and null bytes (CRLF injection)
        if any(ord(c) < 32 or ord(c) == 127 for c in clean_url):
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason="URL contains forbidden control characters or CRLF",
            )

        # 3. Parse URL structure
        try:
            parsed = urlparse(clean_url)
        except Exception as e:
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason=f"Malformed URL structure: {e}",
            )

        # 4. Enforce HTTP / HTTPS schemes exclusively
        if parsed.scheme.lower() not in ("http", "https"):
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason=f"Unsupported protocol scheme '{parsed.scheme}'. Must be HTTP or HTTPS.",
            )

        # 5. Validate hostname presence
        hostname = parsed.hostname
        if not hostname or not hostname.strip():
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason="URL is missing a valid hostname",
            )

        clean_hostname = hostname.lower().strip()

        try:
            port = parsed.port
        except ValueError:
            return URLValidationResult(is_valid=False, original_url=clean_url, rejection_reason="URL contains an invalid port")
        if port is not None and port not in (80, 443):
            return URLValidationResult(is_valid=False, original_url=clean_url, rejection_reason="Nonstandard network ports are not allowed")

        # 6. Reject user credentials in URL (e.g. http://user:pass@example.com)
        if parsed.username or parsed.password:
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason="URL contains embedded user credentials",
            )

        # 7. Check explicit hostname blacklist
        if clean_hostname in PROHIBITED_HOSTNAMES:
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason=f"Prohibited internal hostname: {clean_hostname}",
            )

        # Disallow localhost / 127.0.0.1 nip.io / localtest.me wildcard domains
        if any(bad in clean_hostname for bad in (".nip.io", ".sslip.io", ".localtest.me", "localhost.")):
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason="Prohibited wildcard localhost loopback service domain",
            )

        # 8. Check direct IP address literal
        ip_obj = self._parse_ip_safely(clean_hostname)
        if ip_obj:
            is_bad, reason = self.is_ip_prohibited(ip_obj)
            if is_bad:
                return URLValidationResult(
                    is_valid=False,
                    original_url=clean_url,
                    rejection_reason=f"Prohibited direct IP access: {reason}",
                )

        # 9. Verify domain contains dot (unless IP, non-dot hostnames are internal like 'intranet')
        if not ip_obj and "." not in clean_hostname:
            return URLValidationResult(
                is_valid=False,
                original_url=clean_url,
                rejection_reason=f"Internal un-qualified domain rejected: {clean_hostname}",
            )

        # 10. Check prohibited binary/executable file extensions
        clean_path = (parsed.path or "").lower()
        for ext in PROHIBITED_EXTENSIONS:
            if clean_path.endswith(ext):
                return URLValidationResult(
                    is_valid=False,
                    original_url=clean_url,
                    rejection_reason=f"Prohibited executable/binary file extension: {ext}",
                )

        # 11. Optional DNS Resolution Check (defends against DNS rebinding)
        if self.resolve_dns and not ip_obj:
            try:
                addr_info = socket.getaddrinfo(clean_hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)

                for entry in addr_info:
                    sockaddr = entry[4]
                    resolved_ip_str = sockaddr[0]
                    resolved_ip = self._parse_ip_safely(resolved_ip_str)
                    if resolved_ip:
                        is_bad, reason = self.is_ip_prohibited(resolved_ip)
                        if is_bad:
                            return URLValidationResult(
                                is_valid=False,
                                original_url=clean_url,
                                rejection_reason=f"DNS resolved to prohibited IP ({resolved_ip_str}): {reason}",
                            )
            except (socket.gaierror, socket.timeout) as dns_err:
                logger.debug(f"DNS resolution failed for '{clean_hostname}': {dns_err}")
                return URLValidationResult(
                    is_valid=False,
                    original_url=clean_url,
                    rejection_reason="Hostname could not be safely resolved",
                )

        # 12. Generate canonical normalized URL and deterministic SHA-256 hash
        canonical = normalize_url(clean_url)
        url_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return URLValidationResult(
            is_valid=True,
            original_url=clean_url,
            canonical_url=canonical,
            url_hash=url_hash,
            domain=clean_hostname,
            rejection_reason=None,
        )

    validate_url = validate


