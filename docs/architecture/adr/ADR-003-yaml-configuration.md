# ADR-003: YAML Configuration

## Context

The project needs a way to configure collectors, keywords, scoring, and scheduling without hard-coding behavior into Python modules. Configuration should remain editable by maintainers and easy to review.

## Decision

Static configuration will live in YAML files, especially `config/sources.yaml`, `config/keywords.yaml`, `config/weights.yaml`, and `config/schedule.yaml`.

## Alternatives

- hard-coded Python constants
- JSON files
- database-driven configuration

## Consequences

Configuration is easier to inspect and evolve. The trade-off is that a clear contract is needed so YAML files stay focused on configuration rather than runtime state.

## Future Considerations

If configuration becomes more dynamic, the YAML layer can be extended with validation and versioning rather than moving logic into code.
