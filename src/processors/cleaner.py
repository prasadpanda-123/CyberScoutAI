"""
Opportunity Cleaner Processor for CyberScout AI.
"""

from pathlib import Path
from typing import List, Optional
import urllib.parse
import yaml

from src.core.constants import CONFIG_DIR
from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor
from src.utils.string_utils import clean_html, normalize_whitespace
from src.utils.url_utils import normalize_url


class CleanerProcessor(BaseProcessor):
    """
    Cleans raw HTML markup, whitespace, control characters, and tracking URL parameters.
    """

    def __init__(self, enabled: bool = True, config_file: Optional[Path] = None):
        super().__init__(enabled=enabled)
        self.config_file = config_file or (CONFIG_DIR / "normalization.yaml")
        self.tracking_params: List[str] = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"]
        self.load_configuration()

    @property
    def processor_name(self) -> str:
        return "Cleaner Processor"

    def load_configuration(self) -> None:
        """Loads tracking parameters configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.tracking_params = data.get("tracking_parameters", self.tracking_params)
            except Exception:
                pass

    def _strip_tracking_params(self, url: str) -> str:
        """Strips tracking query parameters from URL string."""
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        query_dict = urllib.parse.parse_qs(parsed.query)
        clean_query = {k: v for k, v in query_dict.items() if k.lower() not in self.tracking_params}
        new_query = urllib.parse.urlencode(clean_query, doseq=True)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        ))

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Cleans Opportunity fields.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Cleaned Opportunity instance.
        """
        if not self.enabled:
            return opportunity

        # Clean title
        clean_t = clean_html(opportunity.title)
        opportunity.title = normalize_whitespace(clean_t)

        # Clean description
        if opportunity.description:
            clean_d = clean_html(opportunity.description)
            opportunity.description = normalize_whitespace(clean_d)

        # Clean URL to canonical representation
        if opportunity.url:
            canonical_url = normalize_url(opportunity.url)
            if canonical_url:
                opportunity.url = canonical_url

        return opportunity
