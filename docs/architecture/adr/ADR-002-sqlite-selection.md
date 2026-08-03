# ADR-002: SQLite Selection

## Context

The project needs a simple, local-first persistence layer for early development and personal use. It should support structured storage, idempotent updates, and future expansion without requiring a full database server.

## Decision

SQLite will be used as the persistence layer for the initial architecture.

## Alternatives

- PostgreSQL
- JSON files only
- No database layer

## Consequences

SQLite keeps the project simple and portable. The trade-off is that the schema and access patterns must remain disciplined as the project grows.

## Future Considerations

If the system becomes multi-user or high-scale, the core data model can be migrated to a more capable database without changing the higher-level architecture.
