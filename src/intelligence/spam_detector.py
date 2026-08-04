"""
Stage 5 & 6: Blacklist & Spam Detection Engine for CyberScout AI.
"""

import re
from typing import List, Optional, Tuple
from src.intelligence.quality_rules import QualityRules


class SpamDetector:
    """
    Stage 5 & Stage 6 Engine inspecting text payloads for blacklisted terms, IPTV playlists,
    excessive URL density, repeated lines, or auto-generated media dumps.
    """

    def __init__(self, rules: Optional[QualityRules] = None):
        self.rules = rules or QualityRules()

    def check_blacklist(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Stage 5: Instant Discard Blacklist Check.

        Args:
            text: Combined content string (title, description, README, topics).

        Returns:
            Tuple of (is_blacklisted, matched_blacklist_term)
        """
        if not text:
            return False, None

        clean_text = text.lower()

        # Hardcoded immediate discard check for IPTV / #EXTM3U / M3U8 / Playlists / Piracy
        immediate_terms = [
            "#extm3u", "iptv", "m3u8", ".m3u", "m3u", "playlist", "playlists",
            "indonesian channels", "television streams", "radio playlist",
            "channel list", "live tv", "free movies", "torrent index",
            "spotify downloader", "netflix downloader", "keygen", "warez",
            "pirated software"
        ]
        for iterm in immediate_terms:
            if iterm in clean_text:
                return True, f"Blacklisted term: '{iterm}'"

        for term in self.rules.blacklist_keywords:
            term_clean = term.lower()
            if len(term_clean) <= 4:
                pattern = rf"\b{re.escape(term_clean)}\b"
                if re.search(pattern, clean_text):
                    return True, term
            else:
                if term_clean in clean_text:
                    return True, term

        return False, None

    def analyze_readme_structure(self, readme: str) -> Tuple[bool, float, Optional[str]]:
        """
        Stage 6: README Structure & Spam Analysis.

        Returns:
            Tuple of (is_spam, spam_score, spam_reason)
        """
        if not readme or not isinstance(readme, str) or not readme.strip():
            return False, 0.0, None

        text = readme.strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # 1. URL Density Check (> 200 URLs or > 50% lines being URLs)
        urls = re.findall(r"https?://[^\s]+", text)
        if len(urls) > self.rules.max_readme_urls:
            return True, 0.95, f"EXCESSIVE_URLS ({len(urls)} URLs exceeds max threshold {self.rules.max_readme_urls})"

        if len(lines) > 20 and (len(urls) / max(1, len(lines))) > 0.6:
            return True, 0.90, "HIGH_URL_DENSITY (Mostly links without technical content)"

        # 2. Repeated Line Check (Spam dumps)
        if len(lines) >= 10:
            unique_lines = set(lines)
            if (len(unique_lines) / len(lines)) < 0.3:
                return True, 0.85, "REPEATED_LINES_SPAM (Repetitive line patterns)"

        # 3. Media Link Density (.m3u, .ts, .mp4, .mkv, .avi)
        media_count = len(re.findall(r"\.(m3u|m3u8|ts|mp4|mkv|avi|mp3|flac)\b", text, re.IGNORECASE))
        if media_count >= 5:
            return True, 0.99, "PLAYLIST_DETECTED (Media file extensions)"

        return False, 0.0, None
