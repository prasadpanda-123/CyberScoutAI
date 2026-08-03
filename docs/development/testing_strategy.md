# Testing Strategy

## Project Testing Philosophy

The project should favor small, deterministic, documentation-backed tests over brittle integration tests. The main goal is to verify that processors and collectors behave correctly under known inputs and that the pipeline remains stable over time.

## 1. Unit Testing

Unit tests should cover:
- validator logic
- cleaner and normalizer functions
- score calculation
- category assignment rules
- date and URL sanitization helpers

Unit tests should be fast, local, and independent of live network access.

## 2. Integration Testing

Integration tests should validate the end-to-end flow for a representative sample pipeline run using fixtures rather than live sources. These tests should confirm that:
- collectors can emit normalized records
- validators and processors transform them correctly
- ranking and storage steps are coordinated correctly

## 3. Collector Fixture Testing

Collector tests should use saved fixture data wherever possible. This makes the tests reproducible and protects them from source churn. Fixture-based tests should verify that a collector still parses the expected structure even when the live site changes.

## 4. Mocking Strategy

Mocks should be used sparingly and only at the network boundary. The project should avoid mocking the behavior of its own business logic. If a collector needs a network response, the test should use a fixture or a local stub rather than a large mock object.

## 5. Database Testing

Database behavior should be tested with a temporary local SQLite database. Tests should verify:
- idempotent upserts
- duplicate handling
- status transitions
- run history persistence

## 6. CI Testing

The continuous integration workflow should run:
- unit tests
- integration tests
- linting or static checks where available

The goal is to catch regressions quickly and keep the repository healthy for contributors.

## 7. Regression Testing

Every bug fix should include a regression test. This is important because the project is built around documented contracts and can regress quietly if a contract changes without explicit tests.

## 8. Coverage Goals

A reasonable initial target is:
- 70%+ coverage for processors and utilities
- 50%+ coverage for collectors
- 100% for critical ranking and validation rules

Coverage goals should be treated as a guardrail, not a substitute for thoughtful tests.

## 9. Definition of Done

A change is considered done when:
- the relevant tests pass
- any new behavior is covered by a regression test
- the documentation remains consistent with the implemented contract

## 10. Testing Folder Organization

The repository should keep tests organized as follows:
- `tests/unit/` for unit-level logic
- `tests/integration/` for pipeline-level flows
- `tests/fixtures/` for saved collector data and sample payloads
