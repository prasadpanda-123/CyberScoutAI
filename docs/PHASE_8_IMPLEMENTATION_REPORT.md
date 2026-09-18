# Phase 8: Advanced Analytics, User Intelligence & Opportunity Insights

## 1. Status

**COMPLETE**

---

## 2. Executive Summary

Phase 8 implements an industrial-grade, deterministic intelligence layer on top of CyberScout AI's opportunity dataset. It answers core user, platform, and administrator questions regarding opportunity velocity, market trends, deadline radar horizons, skill demand, and private interest profiles.

The implementation strictly honors the core architectural commitments:
- **Zero Paid Resources**: 100% Free / Open-Source (PostgreSQL 17 native aggregation, Python standard library, Flask, Jinja2, Tailwind CSS). Zero paid BI, zero external caching, zero Redis/Celery/RabbitMQ/Kafka.
- **Zero Git Mutations**: Zero git-mutating commands were executed (`commit`, `push`, `reset`, `checkout`, `clean`, `restore`).
- **Zero Regressions**: All previous subsystems (Phases 1.1–7: auth, MFA, harvesting, idempotency, SSR search, ranking, quality gating, lifecycle transitions, and notification engine) remain 100% operational and green.
- **Strict Privacy & Isolation**: Multi-tenant data isolation ensures User A only accesses User A's private intelligence; administrators access aggregate telemetry without exposing private user activity.

---

## 3. Analytics Architecture

The Phase 8 architecture is structured into four distinct, decoupled domains:
1. **Platform Opportunity Analytics**: Aggregate opportunity velocity, lifecycle states, economic models, and category/type distributions (`/analytics`).
2. **User Personal Intelligence**: Strictly isolated, private analytics on saved items, calendar deadlines, search queries, and configured career preferences (`/insights`).
3. **Opportunity Trends**: Ingestion velocity comparisons over rolling windows ($7\text{d}, 30\text{d}, 90\text{d}, \text{all time}$) derived deterministically from `first_seen_at`.
4. **Data Quality & Source Health Analytics**: Administrator telemetry monitoring collector yield, malformed rates, latency, quarantine reasons, and Phase 7 notification delivery rates (`/admin/analytics`).

All database access flows from PostgreSQL 17 native aggregations through `AnalyticsRepository`, into `AnalyticsService`, mapped onto strongly typed DTOs (`src/models/analytics_models.py`), and rendered via SSR Jinja2 templates.

---

## 4. Platform Analytics

Platform analytics provide comprehensive market visibility:
- **Total Opportunities**: All canonical records in `"Opportunities"`.
- **Active Pool**: Non-quarantined records with lifecycle state `active` or `closing_soon`.
- **Closing Soon Radar**: Opportunities closing within $\le 3\text{ days}$.
- **Discovery Velocity**: Newly appeared programs in the last 7 days (`first_seen_at >= NOW() - INTERVAL '7 days'`) and 30 days.
- **Economic Breakdown**: Free ($100\%$ free), paid, freemium, and unknown pricing models; programs offering stipends and certificates.
- **Category & Type Breakdown**: Percentage distributions with active count breakdowns.
- **Freshness Health**: Fresh (< 3 days), aging (3–7 days), stale (7–30 days), and severely stale (> 30 days) using Phase 6 temporal thresholds.

---

## 5. User Intelligence

The private `/insights` portal provides personal career telemetry:
- **Saved Portfolio**: Total saved, active saved, closing soon saved, and expired saved counts.
- **Urgent Deadlines Alert**: Highlights saved programs closing within the next 7 days.
- **Interest Radar**: Displays target categories, target opportunity types, and tracked skills from explicit user profile settings and saved opportunities.
- **Search Telemetry**: 30-day frequent search query terms and recent queries with timestamps.
- **Personal Notification Stats**: Total alerts received, unread count, and breakdown by event type (`NEW`, `UPDATED`, `REOPENED`).
- **Safe Empty States**: Clean, helpful guidance when a user has no saved programs or search history yet (zero NaNs or broken layouts).

---

## 6. Opportunity Trends

Trends measure market movement deterministically:
- **Ingestion Velocity**: Aggregated into daily time buckets via `DATE_TRUNC('day', first_seen_at)`.
- **Window Comparison**: Evaluates current window $[T - \Delta, T]$ against prior window $[T - 2\Delta, T - \Delta)$.
- **Division-by-Zero Safety**: Safe calculation when previous period is zero:
  $$\text{percentage\_change} = \begin{cases} 
  0.0 & \text{if } \text{prev} = 0 \text{ and } \text{curr} = 0 \\
  100.0 & \text{if } \text{prev} = 0 \text{ and } \text{curr} > 0 \\
  \text{round}\left(\frac{\text{curr} - \text{prev}}{\text{prev}} \times 100.0, 1\right) & \text{if } \text{prev} > 0 
  \end{cases}$$
- **Creation Invariant**: Trends use `first_seen_at`. `last_harvested_at` is crawler housekeeping and is never treated as opportunity creation.

---

## 7. Deadline Intelligence

Application deadline radar categorizes active opportunities:
- **Due Today**: `deadline = CURRENT_DATE`
- **Due Within 24h**: `deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '1 day'`
- **Due Within 3 Days**: `deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '3 days'`
- **Due Within 7 Days**: `deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '7 days'`
- **Due Within 30 Days**: `deadline >= CURRENT_DATE AND deadline <= CURRENT_DATE + INTERVAL '30 days'`
- **Expired Exclusion**: Expired programs (`deadline < CURRENT_DATE` or `lifecycle_status = 'expired'`) are strictly excluded from future deadline horizons.

---

## 8. Source / Quality Analytics

Reuses Phase 6 `SourceHealth` and `DataQualityEngine` architecture:
- **Collector Telemetry**: Tracks items seen, created, updated, and rejected per registered source.
- **Malformed Rate**: Calculates error rate: $\text{items\_rejected} / \text{items\_seen} \times 100.0$.
- **Source Health States**: Displays `HEALTHY`, `DEGRADED`, `FAILING`, or `DISABLED`.
- **Quarantine Summary**: Tracks quarantined records isolated from active search and breaks down specific quarantine reasons.

---

## 9. Notification Analytics

Integrates with Phase 7 `"NotificationOutbox"`:
- **Outbox Totals**: Total queue records, pending dispatches, sent successfully, and failed deliveries.
- **Retry Monitoring**: Aggregates total attempt counts across workers.
- **Delivery Success Rate**: $\text{sent} / (\text{sent} + \text{failed}) \times 100.0$ with zero-attempt safe fallback.
- **Privacy Preservation**: Metrics provide aggregate counts without leaking sensitive email bodies or recipient credentials.

---

## 10. UI / SSR Implementation

All dashboards adhere to the SSR-first design principle:
- **Progressive Enhancement**: Content renders completely without client JavaScript.
- **Styling**: Tailored with CyberScout AI's existing Tailwind CSS and Stitch Design System tokens (dark mode native, high contrast, clean typography).
- **Accessible Visualizations**: Pure CSS percentage bars and responsive SVG time-series charts.
- **New Routes**:
  - `/analytics`: Public/authenticated platform intelligence.
  - `/insights`: Authenticated private user intelligence.
  - `/admin/analytics`: Authenticated administrative telemetry.

---

## 11. Security / RLS

1. **Authentication & RBAC**:
   - `/analytics` and `/insights` require `@login_required`.
   - `/admin/analytics` requires `@admin_required`.
2. **Row Level Security**:
   - RLS is forced on `"Opportunities"`, `"NotificationOutbox"`, and `"SavedOpportunities"`.
   - Direct user queries enforce `user_id = %s`.
3. **Parameter Binding**:
   - All SQL queries use parameterized placeholders (`%s`), preventing SQL injection.
4. **No Arbitrary Query Endpoints**:
   - Endpoints like `/api/query`, `/api/sql`, `/api/analytics/raw` do not exist.
5. **CSRF Protection**:
   - State-mutating administrative and user forms require valid CSRF tokens.

---

## 12. Database Changes

Zero structural schema migrations were required. Phase 8 derives all analytics directly from existing tables established in prior phases (`"Opportunities"`, `"Sources"`, `"SourceHealth"`, `"SavedOpportunities"`, `"UserPreferences"`, `"UserSearchHistory"`, `"NotificationOutbox"`, `"AuditLogs"`).

---

## 13. Performance Measurements

Live `EXPLAIN ANALYZE` benchmarks on PostgreSQL 17:
- **Platform Overview Aggregation**: 2.67 ms (engine execution)
- **Category Distribution (with percentages)**: 2.08 ms
- **Discovery Velocity Trends (30d)**: 1.48 ms
- **User Personal Intelligence (Saved Join)**: 0.057 ms
- **Full HTTP Request-Response Latency**: 32 ms to 45 ms

---

## 14. Files Changed

### Models & Services
- `src/models/analytics_models.py` [NEW]
- `src/database/analytics_repository.py` [NEW]
- `src/services/analytics_service.py` [NEW]
- `dashboard/services/analytics_service.py` [MODIFY]

### Routes & Controllers
- `dashboard/routes/analytics.py` [MODIFY]
- `dashboard/routes/insights.py` [NEW]
- `dashboard/routes/admin.py` [MODIFY]
- `dashboard/routes/__init__.py` [MODIFY]
- `dashboard/app.py` [MODIFY]

### Templates & Presentation
- `dashboard/templates/analytics.html` [MODIFY]
- `dashboard/templates/insights.html` [NEW]
- `dashboard/templates/admin/admin_analytics.html` [NEW]
- `dashboard/templates/base.html` [MODIFY]
- `dashboard/templates/admin/admin_base.html` [MODIFY]

### Tests & Documentation
- `tests/unit/test_phase8_analytics.py` [NEW]
- `docs/ANALYTICS_ARCHITECTURE.md` [NEW]
- `docs/PHASE_8_IMPLEMENTATION_REPORT.md` [NEW]

---

## 15. Tests

```
Phase 8 tests: 43 / 43 (100% PASSED in 1m 33s)
Phase 7 regression: 46 / 46 (100% PASSED)
Phase 6 regression: 56 / 56 (100% PASSED)
Phase 5 regression: 46 / 46 (100% PASSED)
Phase 4 regression: 42 / 42 (100% PASSED)
Phase 3 regression: 37 / 37 (100% PASSED)
Phase 2.1 regression: 22 / 22 (100% PASSED)
Phase 1.1 regression: 8 / 8 (100% PASSED)

Full suite: 300 / 300 (100% GREEN)
```

---

## 16. Free-Tier Compliance

Paid resources introduced: **0** (Zero paid APIs, zero paid SaaS, zero paid BI, zero external queue or caching services).

---

## 17. Privacy Review

All personal analytics adhere to data minimization:
- No sensitive demographic, political, or psychological profiling.
- Only CyberScout AI opportunity interaction data (bookmarks, searches, career preferences) is analyzed.
- Cross-user data isolation is strictly enforced.

---

## 18. Git Safety

Zero git mutations executed (`commit`, `push`, `reset`, `checkout`, `clean`, `restore`). All git history and branch state remain untouched.

---

## 19. Known Limitations

1. **Small Dataset Variance**: If a category has very few items, percentage changes across short timeframes (e.g. 7 days) can fluctuate sharply.
2. **Browser Timezone Alignment**: Ingestion velocity trends group by UTC day boundaries (`DATE_TRUNC('day', first_seen_at)`).

---

## 20. Final Acceptance Matrix

| Acceptance Criterion | Status | Evidence |
| :--- | :--- | :--- |
| Platform opportunity analytics work | **PASS** | `test_01`, `test_02`, `test_03`, `test_06`, `test_07` |
| Category analytics work | **PASS** | `test_08`, `test_10`, `test_11` |
| Opportunity-type analytics work | **PASS** | `test_09` |
| Deadline intelligence works | **PASS** | `test_12`, `test_13`, `test_14` |
| Economic analytics work where data exists | **PASS** | `test_06` |
| Source analytics use existing SourceHealth semantics | **PASS** | `test_30` |
| Freshness analytics use existing Phase 6 semantics | **PASS** | `AnalyticsRepository.get_freshness_insights()` |
| Quality analytics use existing Phase 6 semantics | **PASS** | `test_31`, `test_32` |
| Trend calculations are deterministic | **PASS** | `test_15`, `test_16`, `test_17`, `test_18`, `test_19` |
| User insights are private | **PASS** | `test_20`, `test_36` |
| User analytics do not leak cross-user information | **PASS** | `test_21` |
| Saved-opportunity analytics work | **PASS** | `test_22` |
| Search-history analytics work where data exists | **PASS** | `test_23` |
| Notification analytics integrate with Phase 7 | **PASS** | `test_26`, `test_27`, `test_28`, `test_29` |
| Admin analytics are RBAC protected | **PASS** | `test_35` |
| Analytics remain SSR-first | **PASS** | Server-side rendered Jinja2 templates |
| JavaScript is progressive enhancement only | **PASS** | CSS/SVG rendered without client JS |
| No arbitrary SQL/query API exists | **PASS** | `test_39` |
| No SQL injection vulnerability exists | **PASS** | `test_38` |
| No XSS vulnerability exists | **PASS** | Auto-escaping in Jinja2 templates |
| RLS remains enforced | **PASS** | `test_37` |
| No sensitive profiling is introduced | **PASS** | Section 17 Privacy Review |
| No unnecessary persistent data is created | **PASS** | Derived directly from existing tables |
| No paid resource is introduced | **PASS** | 100% Free / Open Source |
| No Git-mutating commands are executed | **PASS** | 0 Git mutations |
| Phase 8 tests pass | **PASS** | 43 / 43 (100% Green) |
| Full Phase 1.1–7 regression suite passes | **PASS** | 257 / 257 (100% Green) |
