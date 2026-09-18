"""
Ranking & Personalization Configuration for CyberScout AI.

Defines normalized, bounded weights for multi-signal ranking,
official provider trust tiers, and startup validation routines.
"""

from typing import Dict


DEFAULT_DISCOVERY_WEIGHTS: Dict[str, float] = {
    "skill_match": 0.25,
    "category_match": 0.15,
    "type_match": 0.15,
    "remote_match": 0.10,
    "deadline_urgency": 0.10,
    "freshness": 0.10,
    "source_trust": 0.05,
    "base_quality": 0.05,
    "user_behavior": 0.05,
    "search_relevance": 0.00,
}

DEFAULT_SEARCH_WEIGHTS: Dict[str, float] = {
    "search_relevance": 0.30,
    "skill_match": 0.20,
    "category_match": 0.10,
    "type_match": 0.10,
    "remote_match": 0.05,
    "deadline_urgency": 0.05,
    "freshness": 0.05,
    "source_trust": 0.05,
    "base_quality": 0.05,
    "user_behavior": 0.05,
}

TRUSTED_PROVIDERS = {
    "cisa",
    "owasp",
    "sans institute",
    "sans",
    "google",
    "microsoft",
    "aws",
    "cisco",
    "nist",
    "mitre",
    "us-cert",
    "department of defense",
    "nsa",
}

# Controlled diversity: Max recommendations surfaced from any single organization in the top section
MAX_PER_ORGANIZATION_RECOMMENDATIONS = 2

# Cold-start score threshold for "Strong Match" designation
STRONG_MATCH_THRESHOLD = 0.65
GOOD_MATCH_THRESHOLD = 0.40


def validate_weights(weights: Dict[str, float]) -> bool:
    """
    Validates that a dictionary of weights is bounded, non-negative, and sums to 1.0.

    Args:
        weights: Dictionary mapping feature names to float weights.

    Returns:
        True if valid.

    Raises:
        ValueError: If weights are negative, non-numeric, or do not sum to 1.0.
    """
    if not isinstance(weights, dict) or not weights:
        raise ValueError("Weights must be a non-empty dictionary.")

    total = 0.0
    for key, val in weights.items():
        if not isinstance(val, (int, float)):
            raise ValueError(f"Weight '{key}' must be a numeric value, got {type(val)}.")
        if val < 0.0:
            raise ValueError(f"Weight '{key}' cannot be negative (got {val}).")
        if val > 1.0:
            raise ValueError(f"Weight '{key}' cannot exceed 1.0 (got {val}).")
        total += float(val)

    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0 (got sum={total:.4f}).")

    return True


# Run startup validation on default weight configurations
validate_weights(DEFAULT_DISCOVERY_WEIGHTS)
validate_weights(DEFAULT_SEARCH_WEIGHTS)
