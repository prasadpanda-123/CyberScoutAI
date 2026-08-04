# Security Policy & Responsible Disclosure

CyberScout AI takes security seriously. As a cybersecurity intelligence platform, we strive to maintain the highest security standards across our codebase and dependencies.

---

## 🛡️ Supported Versions

Only the latest release version receives security updates and patches.

| Version | Supported |
|---|---|
| 1.1.x | 🟢 Supported |
| 1.0.x | 🟡 Security Patches Only |
| < 1.0 | 🔴 End of Support |

---

## 🔒 Security Philosophy

- **Zero Hardcoded Secrets**: Credentials, API tokens, and SMTP passwords must strictly be stored in environment variables (`.env`) and never committed to version control.
- **SQL Injection Prevention**: All database queries strictly use parameterized SQL prepared statements.
- **XSS & Input Sanitization**: HTML tags and malicious payloads in feeds are sanitized prior to storage and rendering.
- **Path Safety**: File operations are restricted to `PROJECT_ROOT` boundaries.

---

## 📩 Reporting Vulnerabilities

If you discover a potential security vulnerability in CyberScout AI, please follow our responsible disclosure process:

1. **Do NOT open a public GitHub issue.**
2. Send a detailed report describing the vulnerability, proof of concept, and impact to:
   **security@cyberscout.ai** (or contact the maintainers directly via private channel).
3. We will acknowledge receipt within **24 hours** and provide an estimated fix timeline.
4. Once resolved, we will publish a security patch release and credit your disclosure.
