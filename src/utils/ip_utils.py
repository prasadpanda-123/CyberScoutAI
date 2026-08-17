"""
Centralized Client IP Resolution and Network Utilities for CyberScout AI.

Provides secure, trusted-proxy-aware client IP extraction and validation.
Adheres to OWASP and RFC 7239 guidelines to prevent header spoofing.
"""

import ipaddress
import os
from typing import Any, List, Optional


def _strip_brackets_and_port(clean: str) -> str:
    """Helper to strip IPv4/IPv6 ports and enclosing brackets safely."""
    # Handle bracketed IPv6 with port (e.g. "[2001:db8::1]:8080") or without port ("[2001:db8::1]")
    if clean.startswith("["):
        if "]:" in clean:
            clean = clean.split("]:")[0][1:]
        elif clean.endswith("]"):
            clean = clean[1:-1]
    elif ":" in clean and clean.count(":") == 1:
        # IPv4 with port (e.g. "192.168.1.1:8080")
        clean = clean.split(":")[0]
    return clean


def is_valid_ip(ip_str: Optional[str]) -> bool:
    """
    Validates whether the input string is a valid IPv4 or IPv6 address.
    Never throws an exception.
    """
    if not ip_str or not isinstance(ip_str, str):
        return False
    clean = _strip_brackets_and_port(ip_str.strip())
    try:
        ipaddress.ip_address(clean)
        return True
    except (ValueError, TypeError):
        return False


def normalize_ip(ip_str: Optional[str]) -> Optional[str]:
    """
    Normalizes valid IPv4/IPv6 string and resolves IPv4-mapped IPv6 addresses.
    Returns normalized string or None if invalid.
    """
    if not ip_str or not isinstance(ip_str, str):
        return None
    clean = _strip_brackets_and_port(ip_str.strip())
    try:
        ip_obj = ipaddress.ip_address(clean)
        # Convert IPv4-mapped IPv6 (e.g., ::ffff:192.0.2.1) to standard IPv4
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
            return str(ip_obj.ipv4_mapped)
        return str(ip_obj)
    except (ValueError, TypeError):
        return None


def get_trusted_proxy_count() -> int:
    """
    Determines the number of trusted reverse proxies configured in the deployment environment.
    Defaults:
    - In Render / Cloud hosting (RENDER=true, BEHIND_PROXY=true, APP_ENV=production): defaults to 1
    - In local development: defaults to 0
    """
    env_count = os.environ.get("TRUSTED_PROXY_COUNT")
    if env_count is not None:
        try:
            return max(0, int(env_count))
        except ValueError:
            pass

    # Auto-detect hosted environments (Render, Heroku, AWS, Kubernetes)
    if (
        os.environ.get("RENDER", "").lower() in ("true", "1", "yes")
        or os.environ.get("BEHIND_PROXY", "").lower() in ("true", "1", "yes")
        or os.environ.get("APP_ENV", "").lower() in ("production", "prod", "staging")
    ):
        return 1

    return 0


def get_client_ip(request: Optional[Any] = None) -> str:
    """
    Securely extracts and normalizes the real client IP address from a Flask request.
    
    Security Rules:
    1. If TRUSTED_PROXY_COUNT is 0 (direct connection / local dev), strictly returns
       `request.remote_addr` and ignores untrusted forwarded headers.
    2. If running behind trusted reverse proxies, safely inspects trusted forwarded
       headers in order: CF-Connecting-IP -> X-Real-IP -> X-Forwarded-For -> Forwarded.
    3. Handles multi-hop proxy chains by selecting the client IP before the trusted proxies.
    4. Never throws exceptions on malformed, oversized, or malicious header values.
    5. Always falls back safely to remote_addr or '127.0.0.1'.
    """
    if request is None:
        try:
            from flask import request as flask_req
            request = flask_req
        except Exception:
            return "127.0.0.1"

    direct_ip = normalize_ip(getattr(request, "remote_addr", None)) or "127.0.0.1"

    trusted_proxies = get_trusted_proxy_count()
    if trusted_proxies <= 0:
        # Local development / Direct connection: Do not trust forwarded headers
        return direct_ip

    headers = getattr(request, "headers", {})

    # 1. Cloudflare Connecting IP (if present and valid)
    cf_ip = normalize_ip(headers.get("CF-Connecting-IP"))
    if cf_ip:
        return cf_ip

    # 2. X-Real-IP (if present and valid)
    real_ip = normalize_ip(headers.get("X-Real-IP"))
    if real_ip:
        return real_ip

    # 3. X-Forwarded-For (Chain parsing from right to left)
    xff = headers.get("X-Forwarded-For")
    if xff and isinstance(xff, str):
        hops = [normalize_ip(part.strip()) for part in xff.split(",") if part.strip()]
        valid_hops = [h for h in hops if h is not None]
        if valid_hops:
            # When behind N trusted proxies, the client IP is located at index -(N + 1)
            # If chain length <= trusted_proxies, the first hop is the original client IP
            if len(valid_hops) > trusted_proxies:
                return valid_hops[-(trusted_proxies + 1)]
            return valid_hops[0]

    # 4. RFC 7239 Forwarded header (e.g. for=192.0.2.60;proto=http;by=203.0.113.43)
    forwarded = headers.get("Forwarded")
    if forwarded and isinstance(forwarded, str):
        for part in forwarded.split(";"):
            part = part.strip()
            if part.lower().startswith("for="):
                raw_val = part[4:].strip().strip('"')
                f_ip = normalize_ip(raw_val)
                if f_ip:
                    return f_ip

    # Fallback to direct remote address
    return direct_ip
