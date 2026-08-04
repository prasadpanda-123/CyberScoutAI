# Link Validation Specification (`LINK_VALIDATION.md`)

## Overview

The **Link Validator** (`link_validator.py`) inspects target opportunity URLs for syntax, DNS resolution, and HTTP status codes before indexing.

---

## Validation Checks

1. **Syntax & Scheme**: Asserts `http://` or `https://` schema.
2. **DNS Resolution**: Fast socket DNS lookup to ensure domain resolution.
3. **Status Code**: Rejects dead URLs (404, 410, 500, 502, 503).
4. **Caching**: Caches validation outcomes in-memory to prevent redundant network hits.
