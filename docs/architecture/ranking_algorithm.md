# Ranking Algorithm

## Design Philosophy

The ranking system is intentionally transparent and additive. Every point awarded must be traceable to a documented rule so contributors can inspect and tune the model without needing to retrain anything. In practice, the model is designed around a simple idea: a strong opportunity should be able to reach roughly 100 points, while still being easy to explain and maintain.

The exact weights live in [weights.yaml](../../config/weights.yaml), but the design rationale is documented here so the philosophy stays stable even if the numbers are adjusted later.

---

## Why the Score Exists

The score is not meant to be a mysterious ranking secret. It exists to answer one question clearly: "Which opportunities are most worth surfacing to the user today?"

The model favors opportunities that are:
- affordable or free
- actionable for beginners
- remote or flexible
- credential-bearing
- trustworthy
- time-sensitive

This makes the ranking useful for a student-oriented audience without overfitting to any single source or brand.

## Scoring Factors

| Factor | Weight | Why it exists | Priority |
|---|---:|---|---|
| **Free** | +40 | Cost is the strongest practical signal for the target audience. A free opportunity is often more actionable than a paid one, especially for learners. | P0 |
| **Certificate offered** | +20 | Certificates add tangible resume value and make the opportunity more worthwhile even when the content is otherwise lightweight. | P0 |
| **Remote** | +20 | Remote access removes geographic barriers and increases inclusion for learners who cannot relocate. | P0 |
| **Beginner-friendly** | +15 | The project is aimed at people who are still building skills; this keeps the digest approachable and avoids overemphasizing advanced-only content. | P0 |
| **Recognized provider** | +20 | Trust matters. A well-known provider lowers the risk of low-quality or spam-like listings. | P1 |
| **Deadline soon (≤7 days)** | +10 | Time-sensitive opportunities deserve visibility now; otherwise they become stale before they are seen. | P1 |
| **Duplicate** | −100 | Duplicates should never displace a real opportunity. This penalty effectively removes duplicate records from the candidate set. | P0 |
| **Expired** | excluded upstream | Expired opportunities are filtered out before ranking, so no negative score is needed. | P0 |
| **Unknown source** | 0 | The model deliberately avoids penalizing unknown sources in v1; hidden gems should not be suppressed just because they come from a lesser-known provider. | P2 |

---

## Score Calculation

The core calculation is:

```
score = sum of all applicable positive weights
      + duplicate_penalty (if applicable, effectively zeroing out inclusion)
```

Example — a free, remote, beginner-friendly, certificate-granting opportunity from a recognized provider with no immediate deadline:

```
free:                +40
certificate_offered: +20
remote:               +20
beginner_friendly:    +15
recognized_provider:  +20
deadline_soon:         +0
──────────────────────────
total:                115
```

The numbers are intentionally simple, and they are meant to be explainable to a contributor reading the code or the docs later.

## Inclusion Threshold

The daily email uses a configurable threshold from [weights.yaml](../../config/weights.yaml). The default threshold is 50. This means an opportunity needs to show at least one strong signal beyond the cost signal to be considered worth emailing. A pure-noise item with no positive features should score 0 and be excluded automatically.

## Category Balancing

Raw score ordering can overwhelm a digest with one category. After ranking, the email layer applies soft category balancing so the digest remains varied. This is a presentation layer concern and should not replace the underlying score itself.

## Future Improvements

1. **Personalized weight overrides** — later phases could let users boost certain keywords or categories.
2. **Staleness decay** — very old opportunities could lose momentum if they repeatedly fail to qualify.
3. **Engagement-informed trust** — provider trust could eventually be learned from user engagement rather than a static list.
4. **Local AI-assisted quality scoring** — optional and supplementary, not a replacement for the transparent additive model.
5. **Category-specific weight profiles** — future variants could tune some weights differently for internships, CTFs, and courses.

These improvements are intentionally deferred; the v1 model's strength is simplicity and auditability.
