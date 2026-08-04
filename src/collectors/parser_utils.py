"""
Parser Utility Functions for CyberScout AI Collectors.

Provides HTML text extraction, URL canonicalization, and robust RSS/XML parsing
with detailed diagnostic logging and multi-stage fallback recovery.
"""

import json
from html import unescape
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from src.core.logging import get_logger
from src.core.rss_diagnostics import RSSDiagnosticsManager

logger = get_logger(__name__)


def parse_json_content(content: str) -> Any:
    """
    Parses JSON content string safely.

    Args:
        content: Input JSON string.

    Returns:
        Parsed JSON object or None on error.
    """
    if not content or not isinstance(content, str) or not content.strip():
        return None
    try:
        return json.loads(content)
    except Exception as e:
        logger.warning(f"JSON parsing failed: {e}")
        return None


def parse_html_content(content: str) -> Any:
    """
    Parses HTML content safely into a light element lookup wrapper.

    Args:
        content: Input HTML string.

    Returns:
        SimpleSoup object.
    """
    if not content or not isinstance(content, str):
        content = ""

    class SimpleTag:
        def __init__(self, name: str, text: str):
            self.name = name
            self.text = text

    class SimpleSoup:
        def __init__(self, raw: str):
            self.raw = raw
            self.text = clean_html(raw)

        def find(self, name: str) -> Optional[SimpleTag]:
            match = re.search(rf"<{name}[^>]*>(.*?)</{name}>", self.raw, re.IGNORECASE | re.DOTALL)
            if match:
                return SimpleTag(name, clean_html(match.group(1)))
            return None

    return SimpleSoup(content)


def clean_html(raw_html: str) -> str:
    """
    Strips HTML tags, decodes HTML entities, and normalizes whitespace.

    Args:
        raw_html: Input HTML string.

    Returns:
        Clean plain text string.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""
    text = re.sub(r"<style.*?>.*?</style>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_rss_xml_content(
    content: str,
    source_id: str = "unknown",
    url: str = "",
    collector_name: str = "Generic RSS Collector",
    status_code: int = 200,
    content_type: str = "text/xml",
) -> List[Dict[str, Any]]:
    """
    Parses RSS/Atom XML feed content into a normalized list of item dictionaries,
    with automatic HTML/JSON detection, error diagnostic logging, and fallback recovery.

    Args:
        content: Raw XML string.
        source_id: Source ID string.
        url: Target feed URL.
        collector_name: Name of collector.
        status_code: HTTP status code.
        content_type: Content-Type header string.

    Returns:
        List of dictionaries with keys: title, link, description, published_date.
    """
    if not content or not isinstance(content, str) or not content.strip():
        return []

    cleaned_content = content.strip()
    diag_mgr = RSSDiagnosticsManager()

    # 1. Content-Type and Payload Inspection for HTML / Cloudflare
    lower_payload = cleaned_content.lower()
    lower_ct = content_type.lower() if content_type else ""

    is_html = (
        "text/html" in lower_ct
        or lower_payload.startswith(("<!doctype html", "<html"))
        or "just a moment..." in lower_payload
        or "cf-browser-verification" in lower_payload
    )

    if is_html:
        diag_mgr.log_parser_error(
            source_id=source_id,
            collector_name=collector_name,
            target_url=url,
            http_status=status_code,
            content_type=content_type,
            payload=content,
            exception_msg="Response is HTML/Cloudflare page instead of XML.",
            recommendation="Recommend switching to 'HtmlScraperCollector' (Response is HTML).",
        )
        return []

    # 2. Content-Type Inspection for JSON
    is_json = "application/json" in lower_ct or cleaned_content.startswith(("{", "["))
    if is_json:
        diag_mgr.log_parser_error(
            source_id=source_id,
            collector_name=collector_name,
            target_url=url,
            http_status=status_code,
            content_type=content_type,
            payload=content,
            exception_msg="Response is JSON format instead of XML.",
            recommendation="Recommend switching to API/JSON Collector (Response is JSON).",
        )
        return []

    # 3. Attempt Standard ElementTree Parsing
    try:
        items = _extract_items_from_xml(cleaned_content)
        diag_mgr.record_success(source_id=source_id, target_url=url)
        return items
    except ET.ParseError as pe:
        line, col = pe.position if hasattr(pe, "position") else (None, None)
        err_msg = str(pe)

        diag_mgr.log_parser_error(
            source_id=source_id,
            collector_name=collector_name,
            target_url=url,
            http_status=status_code,
            content_type=content_type,
            payload=content,
            exception_msg=err_msg,
            line=line,
            col=col,
        )

        # 4. Fallback Recovery Stage 1: lxml (if available)
        recovered_items = _try_lxml_recovery(content)
        if recovered_items is not None:
            logger.info(f"lxml recovery succeeded for provider '{source_id}' ({len(recovered_items)} items recovered).")
            return recovered_items

        # 5. Fallback Recovery Stage 2: Entity & Control Character Sanitization
        sanitized = _sanitize_malformed_xml(content)
        try:
            items = _extract_items_from_xml(sanitized)
            logger.info(f"Sanitization recovery succeeded for provider '{source_id}' ({len(items)} items recovered).")
            return items
        except Exception:
            pass

        return []
    except Exception as e:
        diag_mgr.log_parser_error(
            source_id=source_id,
            collector_name=collector_name,
            target_url=url,
            http_status=status_code,
            content_type=content_type,
            payload=content,
            exception_msg=str(e),
        )
        return []


def _extract_items_from_xml(xml_content: str) -> List[Dict[str, Any]]:
    """Helper to parse RSS 2.0 or Atom elements from valid XML tree."""
    root = ET.fromstring(xml_content)
    items: List[Dict[str, Any]] = []

    # RSS 2.0 channel items
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")

            title = title_el.text.strip() if title_el is not None and title_el.text else "Untitled"
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
            pub = pub_el.text.strip() if pub_el is not None and pub_el.text else ""

            items.append({
                "title": title,
                "link": link,
                "description": desc,
                "published_date": pub,
            })
        return items

    # Atom feed entries
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        title_el = entry.find("{http://www.w3.org/2005/Atom}title")
        link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        summary_el = entry.find("{http://www.w3.org/2005/Atom}summary")
        pub_el = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")

        title = title_el.text.strip() if title_el is not None and title_el.text else "Untitled"
        link = link_el.attrib.get("href", "") if link_el is not None else ""
        desc = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
        pub = pub_el.text.strip() if pub_el is not None and pub_el.text else ""

        items.append({
            "title": title,
            "link": link,
            "description": desc,
            "published_date": pub,
        })

    return items


def _try_lxml_recovery(xml_content: str) -> Optional[List[Dict[str, Any]]]:
    """Attempts XML parsing using lxml parser with recover=True if installed."""
    try:
        from lxml import etree as lxml_etree
        lxml_parser = lxml_etree.XMLParser(recover=True, encoding="utf-8")
        root = lxml_etree.fromstring(xml_content.encode("utf-8"), parser=lxml_parser)
        
        items: List[Dict[str, Any]] = []
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                pub_el = item.find("pubDate")

                title = title_el.text.strip() if title_el is not None and title_el.text is not None else "Untitled"
                link = link_el.text.strip() if link_el is not None and link_el.text is not None else ""
                desc = desc_el.text.strip() if desc_el is not None and desc_el.text is not None else ""
                pub = pub_el.text.strip() if pub_el is not None and pub_el.text is not None else ""

                items.append({
                    "title": title,
                    "link": link,
                    "description": desc,
                    "published_date": pub,
                })
            return items

        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            summary_el = entry.find("{http://www.w3.org/2005/Atom}summary")
            pub_el = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")

            title = title_el.text.strip() if title_el is not None and title_el.text is not None else "Untitled"
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            desc = summary_el.text.strip() if summary_el is not None and summary_el.text is not None else ""
            pub = pub_el.text.strip() if pub_el is not None and pub_el.text is not None else ""

            items.append({
                "title": title,
                "link": link,
                "description": desc,
                "published_date": pub,
            })

        return items
    except ImportError:
        return None
    except Exception:
        return None


def _sanitize_malformed_xml(raw_xml: str) -> str:
    """Sanitizes unescaped ampersands and non-printable control characters in XML."""
    # Strip invalid control characters
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", raw_xml)
    # Fix unescaped ampersands not part of valid entity reference
    sanitized = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", sanitized)
    return sanitized


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Cleans and converts relative URLs into canonical absolute URLs.

    Args:
        url: Raw URL string.
        base_url: Optional base URL for resolving relative links.

    Returns:
        Clean absolute URL string.
    """
    url_clean = url.strip()
    if not url_clean:
        return ""
    if base_url and not url_clean.startswith(("http://", "https://")):
        url_clean = urllib.parse.urljoin(base_url, url_clean)
    return url_clean
