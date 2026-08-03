# Contributing to CyberScout AI

## Repository Setup

1. Clone the repository and create a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Review the architecture documents in `docs/architecture/` before making changes.
4. Keep configuration changes in `config/` and avoid committing secrets.

## Development Workflow

- Create a feature branch from the main branch.
- Make small, focused changes.
- Update documentation when behavior or contracts change.
- Run relevant tests before requesting review.

## Coding Standards

- Prefer readable, well-documented Python code.
- Keep modules focused on a single responsibility.
- Follow the existing architecture boundaries between collectors, processors, intelligence, database, and notifier layers.
- Avoid introducing new configuration into code when YAML can express it instead.

## Branch Strategy

- `main` is the stable branch.
- Use short-lived feature branches for work.
- Use descriptive branch names such as `docs/architecture-consistency` or `feature/collector-health`.

## Commit Message Conventions

Use concise, descriptive commit messages such as:
- `docs: align opportunity model terminology`
- `docs: add collector health strategy`
- `docs: add testing strategy`

## Pull Request Checklist

- Documentation is updated when contracts change.
- Tests were added or updated for the affected behavior.
- The change does not introduce contradictions with the architecture documents.
- The PR description clearly explains the intent and scope.

## Collector Development Guide

When adding a collector:
- implement the contract defined in `docs/architecture/collector_contract.md`
- register the source in `config/sources.yaml`
- preserve the original payload in `raw_data`
- keep the collector responsible only for fetch/parse behavior

## Documentation Requirements

- Keep documentation accurate and consistent with the current architecture.
- Use the canonical field names and enums from the architecture docs.
- Link to related documents instead of duplicating content unnecessarily.

## Testing Requirements

- Add or update tests for any behavior change.
- Prefer fixture-based tests for collectors and processors.
- Include regression tests for bug fixes.

## Definition of Done

A task is considered complete when:
- the intended behavior is documented
- the relevant tests pass
- the change is understandable to the next contributor
