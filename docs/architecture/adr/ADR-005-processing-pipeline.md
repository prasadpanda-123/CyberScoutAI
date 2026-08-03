# ADR-005: Processing Pipeline

## Context

Raw source data must pass through several stages before it becomes actionable: validation, cleaning, normalization, deduplication, categorization, ranking, and storage. These stages need to be separated so failures and logic changes remain contained.

## Decision

The project will use a staged processing pipeline in which each stage transforms the shared `Opportunity` shape and does not need to know the internal details of the previous stage.

## Alternatives

- one large processing function
- inline logic inside collectors

## Consequences

The pipeline becomes easier to reason about and test. The trade-off is that data contracts must be preserved across each stage.

## Future Considerations

The pipeline can gain additional stages later without forcing a redesign if the contracts remain stable.
