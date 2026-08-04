"""
Feature 5: Advanced Semantic Duplicate Engine for CyberScout AI (Phase 12).
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from src.models.opportunity import Opportunity


class SemanticDuplicateEngine:
    """
    Intelligent semantic duplicate detector comparing normalized title signatures,
    organization terms, year variants (e.g. GSoC 2026 vs GSoC 2027 vs GSoC Internship),
    and URL hashes to merge duplicates seamlessly.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.seen_signatures: Dict[str, Opportunity] = {}

    def normalize_title(self, title: str) -> str:
        """Normalizes title string for semantic token comparison."""
        if not title:
            return ""
        text = title.lower().strip()
        text = re.sub(r"[\d]{4}", "", text)  # remove year digits (2026, 2027)
        text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
        tokens = sorted([w for w in text.split() if len(w) > 2])
        return " ".join(tokens)

    def calculate_similarity(self, sig1: str, sig2: str) -> float:
        """Calculates Jaccard similarity score between token signatures."""
        set1 = set(sig1.split())
        set2 = set(sig2.split())
        if not set1 or not set2:
            return 0.0
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        return len(intersection) / len(union)

    def process_batch(self, opportunities: List[Opportunity]) -> Tuple[List[Opportunity], List[Opportunity]]:
        """
        Deduplicates opportunities batch.

        Returns:
            Tuple of (unique_opportunities, merged_duplicates)
        """
        unique: List[Opportunity] = []
        merged: List[Opportunity] = []

        for opp in opportunities:
            sig = self.normalize_title(opp.title)
            url_hash = opp.generate_url_hash()
            is_dupe = False

            # 1. URL Hash check
            if url_hash in self.seen_signatures:
                opp.status = "duplicate"
                opp.duplicate_of_id = self.seen_signatures[url_hash].id
                merged.append(opp)
                continue

            # 2. Semantic Signature check
            for existing_sig, existing_opp in list(self.seen_signatures.items()):
                if len(sig) > 5 and len(existing_sig) > 5:
                    sim = self.calculate_similarity(sig, existing_sig)
                    if sim >= self.similarity_threshold:
                        opp.status = "duplicate"
                        opp.duplicate_of_id = existing_opp.id
                        is_dupe = True
                        merged.append(opp)
                        break

            if not is_dupe:
                self.seen_signatures[sig] = opp
                self.seen_signatures[url_hash] = opp
                unique.append(opp)

        return unique, merged
