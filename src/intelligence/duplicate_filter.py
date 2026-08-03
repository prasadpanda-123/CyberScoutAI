"""
Duplicate Filter for CyberScout AI Intelligence Layer.
"""

from typing import Dict, List

from src.models.opportunity import Opportunity


class DuplicateFilter:
    """
    Deduplicates a batch of ranked opportunities, preserving the highest-scoring version.
    """

    def filter_duplicates(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """
        Deduplicates opportunities by canonical URL hash, retaining the item with highest score.

        Args:
            opportunities: List of ranked Opportunity objects.

        Returns:
            List of unique, highest-ranked Opportunity objects.
        """
        best_map: Dict[str, Opportunity] = {}

        for opp in opportunities:
            url_hash = opp.generate_url_hash()
            if url_hash not in best_map:
                best_map[url_hash] = opp
            else:
                existing = best_map[url_hash]
                if opp.score > existing.score:
                    best_map[url_hash] = opp

        return list(best_map.values())
