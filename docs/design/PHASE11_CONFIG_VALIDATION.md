# Phase 11 — Configuration & Source Validation Framework Specification

**Version:** v1.1.2  
**Target Tag:** `v1.1.2-config-validation`  
**Status:** Released

---

## 1. Architecture Overview

The Configuration & Source Validation Framework enforces fast fail-safe verification of all project YAML definitions, provider capabilities, collector class mappings, and URL syntax prior to pipeline execution.

```text
+-------------------------------------------------------------------------------+
|              CONFIGURATION & SOURCE VALIDATION ARCHITECTURE                   |
|                                                                               |
|  [ YAML Config Files (config/*.yaml) ]                                        |
|        │                                                                      |
|        ▼                                                                      |
|  [ ConfigurationValidator (src/core/config_validator.py) ]                    |
|        ├─ Audits YAML syntax & duplicate keys                                 |
|        ├─ Verifies mandatory fields (id, name, base_url)                      |
|        └─ Validates category capabilities & priority levels                   |
|        │                                                                      |
|        ▼                                                                      |
|  [ ProviderHealthChecker (src/core/provider_health.py) ]                      |
|        ├─ Validates DNS resolution via socket.getaddrinfo                     |
|        ├─ Checks collector class registration in CollectorRegistry           |
|        └─ Assigns status: Healthy | Warning | Broken | Disabled               |
|        │                                                                      |
|        ▼                                                                      |
|  [ URL Sanitizer & Normalizer (src/utils/url_utils.py) ]                      |
|        ├─ Normalizes protocols & removes duplicate slashes                    |
|        ├─ Replaces invalid hostname underscores (portswigger_academy.com)     |
|        └─ Blocks dangerous schemes (file://, ftp://, localhost)               |
+-------------------------------------------------------------------------------+
```

---

## 2. Dynamic CLI Diagnostic Commands

```bash
# Audit YAML configuration and collector mappings
python main.py --validate-config

# Audit provider sources and capability matrices
python main.py --validate-sources

# Run live DNS resolution and reachability health checks
python main.py --provider-health

# Display master configuration audit summary report
python main.py --config-report
```
