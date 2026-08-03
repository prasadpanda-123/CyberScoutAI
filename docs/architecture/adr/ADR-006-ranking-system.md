# ADR-006: Ranking System

## Context

The project needs a simple way to decide which opportunities are worthy of surfacing to the user. A black-box model would be hard to inspect, tune, and trust.

## Decision

The ranking system will use a transparent additive scoring model with documented factors and weights.

## Alternatives

- machine-learning ranking
- manual curation only
- opaque rule-based heuristics

## Consequences

The system is understandable and easy to tune. The trade-off is that the model is simpler than a fully learned ranking system and may need future refinement as usage data grows.

## Future Considerations

The additive model can evolve with more factors or personalization later, but it should remain explainable.
