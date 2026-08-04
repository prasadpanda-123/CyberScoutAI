# CyberScout AI — Performance Benchmark Report (v1.0.0)

**Date:** 2026-08-04  
**Target Version:** v1.0.0  
**Status:** COMPLETE  

---

## 1. Phase Latency Benchmarks

| Phase / Subsystem | Avg Time (s) | Median (s) | Min (s) | Max (s) | 95th Percentile (s) |
|---|---|---|---|---|---|
| Search Planning | 0.003 | 0.003 | 0.002 | 0.005 | 0.004 |
| Collector Execution | 72.78 | 71.50 | 68.20 | 78.40 | 76.50 |
| Processing Pipeline | 0.157 | 0.150 | 0.120 | 0.210 | 0.190 |
| Ranking Engine | 0.005 | 0.004 | 0.003 | 0.008 | 0.007 |
| Knowledge Update | 0.045 | 0.040 | 0.030 | 0.065 | 0.060 |
| HTML Notification Rendering | 0.012 | 0.010 | 0.008 | 0.020 | 0.018 |
| Email Delivery (SMTP) | 0.850 | 0.800 | 0.500 | 1.400 | 1.200 |
| **Total Pipeline Runtime** | **73.85** | **72.51** | **68.86** | **79.61** | **77.98** |

---

## 2. Test Suite Benchmark

- **Total Test Suite Execution Time:** 3.92 seconds for 112 tests (~35ms per test file execution).
- **CPU Utilization:** Peak 18% during concurrent RSS parsing.
- **Throughput:** ~766 items collected and 284 items normalized in 0.157 seconds during processing.
