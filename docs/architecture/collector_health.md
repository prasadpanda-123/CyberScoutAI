# Collector Health Strategy

## Purpose

The collector health strategy defines how the project evaluates whether a collector is healthy, broken, or needs maintenance. The goal is to make source failures visible before they affect the daily digest.

## 1. Collector Validation

Each collector should be validated at three levels:
- configuration validation
- fetch/parse validation
- result quality validation

Configuration validation checks that required credentials or endpoints are available. Fetch/parse validation checks whether the collector can successfully retrieve and interpret the source. Result quality validation checks whether the emitted items are meaningful and structurally compatible with the canonical `Opportunity` model.

## 2. Broken Collector Detection

A collector should be treated as broken when one or more of the following conditions are observed:
- repeated failed runs
- parse failures that exceed the configured threshold
- returned items that fail minimal validation consistently
- source structure changes that make the collector produce empty or malformed output

Broken collectors should be surfaced in health reporting and should not silently continue producing misleading results.

## 3. Sample Extraction

Each collector should be able to produce a small sample payload for review. These samples are useful for:
- debugging collector regressions
- reviewing schema drift
- documenting expected output for future maintainers

Samples should be stored as fixtures or documentation examples rather than hard-coded in the runtime code path.

## 4. Health Scoring

A simple health score can be used to prioritize maintenance:
- 80–100: healthy
- 60–79: degraded but functional
- 40–59: needs review
- below 40: broken or high-risk

The score may be based on run success rate, parse quality, and freshness of last successful collection.

## 5. Retry Policy

Transient failures should be retried with backoff. Permanent failures should not be retried indefinitely. A collector that keeps failing for a sustained period should be marked degraded and require manual review.

## 6. Maintenance Strategy

Collectors should be reviewed periodically for:
- endpoint changes
- authentication changes
- parser drift
- rate limiting issues
- excessive empty responses

Maintenance should be lightweight and documentation-driven so that contributors can understand why a collector is failing and how to fix it.

## 7. Future Automation

In later phases, health status can be automated through:
- scheduled health checks
- alerting on repeated failures
- automatic quarantine of severely broken collectors
- health dashboards that summarize source reliability over time

These are future improvements; the architecture remains simple and explicit in v1.
