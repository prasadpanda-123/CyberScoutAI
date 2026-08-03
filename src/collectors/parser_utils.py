"""
Parser Utilities for CyberScout AI Collection Framework.

Provides RSS/Atom XML parsing, JSON parsing, HTML string/element parsing,
ISO date normalization, and URL cleanup helpers.
"""

from datetime import datetime, timezone

from html.parser import HTMLParser
import json
import re
from typing import Any, Dict, List, Optional
import urllib.parse
import xml.etree.ElementTree as ET

from src.collectors.exceptions import ParsingError
from src.core.logging import get_logger

logger = get_logger(__name__)


def parse_json_content(content: str) -> Any:
    """Parses raw JSON string into Python data object."""
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ParsingError(f"Failed to parse JSON content: {e}", original_exception=e)


def parse_html_content(content: str) -> Any:
    """
    Parses raw HTML string using BeautifulSoup if available, or fallback HTML parser.

    Args:
        content: Raw HTML text content.

    Returns:
        BeautifulSoup object or fallback parser dict.
    """
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(content, "html.parser")
    except ImportError:
        logger.debug("bs4 not installed. Using standard library HTML Parser fallback.")
        # Minimal fallback DOM structure wrapper
        class SimpleTag:
            def __init__(self, name: str, text: str):
                self.name = name
                self.text = text

        class SimpleSoup:
            def __init__(self, text: str):
                self.text = text

            def find(self, name: str) -> Optional[SimpleTag]:
                match = re.search(rf"<{name}[^>]*>(.*?)</{name}>", self.text, re.IGNORECASE | re.DOTALL)
                if match:
                    return SimpleTag(name, match.group(1).strip())
                return None

        return SimpleSoup(content)


def parse_rss_xml_content(content: str) -> List[Dict[str, Any]]:
    """
    Parses RSS/Atom XML feed content into a normalized list of item dictionaries.

    Args:
        content: Raw XML string.

    Returns:
        List of dictionaries with keys: title, link, description, published_date.
    """
    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(content)
        # Check RSS channel items
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

        # Check Atom feed entries
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
    except Exception as e:
        logger.warning(f"XML ET parsing failed ({e}). Returning empty item list.")
        return items


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

    # Remove tracking fragments
    parsed = urllib.parse.urlparse(url_clean)
    cleaned = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        "",  # Strip fragment
    ))
    return cleaned
