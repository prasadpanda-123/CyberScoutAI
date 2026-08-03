# ADR-004: Collector Plugin Architecture

## Context

The project needs to support many different sources, and those sources have different fetch methods and parsing requirements. A plugin-like collector architecture keeps the pipeline consistent while allowing source-specific implementation.

## Decision

Collectors will be implemented as independently runnable modules that conform to the collector contract and are registered through configuration.

## Alternatives

- a single monolithic scraper
- source-specific logic embedded in the scheduler

## Consequences

The pipeline can grow to support many collectors without changing the central orchestration. The trade-off is that each collector must respect the contract and remain isolated.

## Future Considerations

The current architecture is compatible with future plugin packaging if the project later wants community-contributed collectors.
