# Source Reliability Engine Specification (`PROVIDER_RELIABILITY.md`)

## Overview

Every opportunity provider source in CyberScout AI is assigned a dynamic **Reliability Score (0–100)** and a **1–5 Star Rating** calculated continuously from network health telemetry.

---

## Star Rating Matrix

| Reliability Score | Star Rating | Category / Trust Level |
|---|---|---|
| 90.0 – 100.0 | ★★★★★ | Verified Official Provider (CISA, US-CERT, GitHub API, CTFtime, OWASP, PortSwigger) |
| 75.0 – 89.9 | ★★★★☆ | Trusted Community Provider (HackTheBox, TryHackMe) |
| 60.0 – 74.9 | ★★★☆☆ | Standard RSS Provider |
| 40.0 – 59.9 | ★★☆☆☆ | Scraper / HTML Provider |
| < 40.0 | ★☆☆☆☆ | Degraded / Unreliable Provider |

---

## Score Formula & Telemetry Metrics

- `success_rate`: Percentage of successful HTTP responses.
- `failure_rate`: Percentage of failed requests or connection resets.
- `dns_failures`: Count of domain resolution failures.
- `timeouts`: Count of socket timeouts.
- `consecutive_failures`: Penalty factor multiplying rapid retries.
- `average_response_time`: Speed bonus/penalty multiplier.
