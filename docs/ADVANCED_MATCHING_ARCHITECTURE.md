# CyberScout AI — Advanced Opportunity Intelligence & Explainable Matching Architecture (Phase 9)

## 1. Executive Summary

Phase 9 introduces deterministic, explainable, and auditable opportunity matching and similarity intelligence to CyberScout AI. Built entirely on PostgreSQL-native mechanisms, deterministic Python evaluation, and server-side rendering (SSR), Phase 9 provides transparent answers to critical user questions:
- **"Why is this opportunity relevant to me?"**
- **"Which opportunities are genuinely similar?"**
- **"Which of my skills match this opportunity?"**
- **"What important requirements am I missing?"**
- **"How strongly does this opportunity match my stated interests?"**

In strict adherence to the project's zero-cost open-source philosophy, Phase 9 **does not** introduce paid LLM APIs, opaque vector databases, third-party recommendation engines, or cloud machine learning pipelines. All matching is auditable, deterministic, and privacy-preserving.

---

## 2. Architectural Pipeline

The Phase 9 processing flow seamlessly integrates with Phase 5 (Ranking & Personalization), Phase 6 (Quality, Lifecycle & Freshness), Phase 7 (Notifications), and Phase 8 (Analytics):

```
       Opportunity Data Source
                 │
                 ▼
       Phase 6 Quality & Lifecycle Gate (Exclude Quarantined / Stale / Expired)
                 │
                 ▼
       Phase 9 Skill & Feature Normalization
                 │
                 ├───► Eligibility Evaluation (Phase 5 EligibilityChecker)
                 │         │ (Status: ELIGIBLE / INELIGIBLE / UNKNOWN)
                 │         │ [Strictly decoupled from ranking score]
                 │
                 ├───► Explainable Match Analysis (MatchAnalyzer)
                 │         │ (MATCHED / PARTIAL_MATCH / MISSING / UNKNOWN)
                 │         │ Dimension scores & factual audit statements
                 │
                 └───► Deterministic Similarity Engine (SimilarityEngine)
                           │ Stage 1: Candidate Generation (SQL Category/Type/Tag filter, LIMIT 50)
                           │ Stage 2: Multi-attribute scoring & organization diversity
                           │ (Self-excluded, canonical records only)
                                 │
                                 ▼
                     Phase 5 Unified Ranking Service
                                 │
                                 ▼
                     SSR Opportunity Presentation (/opportunities/<id>)
```

---

## 3. Skill Normalization Engine

### 3.1 Normalization Invariants
Skills extracted from opportunities and user profiles are processed through `src/intelligence/skill_normalizer.py`:
1. **Case Normalization**: Case folding to lower case (`"Python"` → `"python"`, `"PYTHON"` → `"python"`).
2. **Whitespace Collapsing**: Stripping leading/trailing spaces and reducing multi-space or tab sequences to single spaces (`"  burp    suite  "` → `"burp suite"`).
3. **Alias Canonicalization**: Controlled alias maps for industry-standard abbreviations (e.g., `"golang"` → `"go"`, `"k8s"` → `"kubernetes"`, `"reactjs"` → `"react"`, `"postgres"` → `"postgresql"`).
4. **Distinct Technology Isolation**: Explicit prevention of hazardous substring or partial matches:
   - `java` != `javascript`
   - `c` != `c++` != `c#`
   - `python` != `cython`
5. **Length & Cardinality Bounding**: Max 50 characters per skill, max 50 skills per user profile, preventing memory exhaustion or Denial of Service.

---

## 4. Explainable Match Analysis

### 4.1 Match Categories
When comparing an opportunity against a user profile, matching falls into discrete, transparent categories:
- **`MATCHED`**: Opportunity requires structured skills and 100% are covered in the user profile.
- **`PARTIAL_MATCH`**: Opportunity requires multiple skills and at least one (but not all) is covered.
- **`MISSING`**: Opportunity specifies skills, but none appear in the user's declared profile.
- **`UNKNOWN`**: Opportunity specifies no required skills, or user has declared no profile skills.

### 4.2 Missing Profile Skills Representation
To respect user privacy and avoid making unsupported assertions:
- Skills listed on an opportunity but absent from the user's profile are explicitly labeled:
  **"Skills not currently listed in your profile"**
- The system **never** claims the user lacks the skill or lacks ability, preserving dignity and auditability.

### 4.3 Deterministic Match Scoring Formula
The match score between an opportunity $O$ and user profile $U$ is defined as:
$$S_{match} = w_{skill} \cdot S_{skill} + w_{cat} \cdot S_{cat} + w_{type} \cdot S_{type} + w_{remote} \cdot S_{remote} + w_{loc} \cdot S_{loc} + w_{behavior} \cdot S_{behavior}$$

Where standard weights configured in `ranking_config.py` sum to 1.0:
- $w_{skill} = 0.35$ (Jaccard skill coverage ratio)
- $w_{cat} = 0.20$ (Binary category match)
- $w_{type} = 0.15$ (Binary opportunity type match)
- $w_{remote} = 0.10$ (Remote preference compatibility)
- $w_{loc} = 0.10$ (Location match)
- $w_{behavior} = 0.10$ (Historical search or saved opportunity affinity)

Every component generates factual explanations (e.g., *"Matches your Cybersecurity preference"*, *"3 of 4 listed skills match your profile"*).

---

## 5. Opportunity-to-Opportunity Similarity

### 5.1 Two-Stage Architecture
To prevent $O(N)$ candidate retrieval or full table scans:
1. **Stage 1 — PostgreSQL Candidate Retrieval**:
   SQL query filters active, non-stale, non-quarantined candidates matching the target category, type, or tags:
   ```sql
   SELECT id, title, category, opportunity_type, provider, tags, score, deadline, is_remote, location
   FROM "Opportunities"
   WHERE id != %s
     AND status = 'active'
     AND data_quality_state != 'quarantined'
     AND (freshness_state != 'severely_stale' OR freshness_state IS NULL)
     AND (category = %s OR opportunity_type = %s OR tags && %s)
   ORDER BY score DESC
   LIMIT 50;
   ```
2. **Stage 2 — Deterministic In-Memory Scoring**:
   Candidate scores are computed using weighted attribute overlap:
   - Category match: 0.35
   - Opportunity type match: 0.25
   - Normalized tag/skill Jaccard overlap: 0.25
   - Provider overlap: 0.10
   - Remote flag match: 0.05

### 5.2 Deterministic Ordering & Tie-Breaking
Candidates are ordered by:
1. `similarity_score DESC`
2. `base_quality DESC`
3. `opportunity_id ASC`

### 5.3 Provider / Organization Diversity
To ensure diverse recommendation sets, the similarity engine enforces a maximum of 2 opportunities per provider/organization (unless total candidates are exhausted).

---

## 6. Strict Separation of Concerns

CyberScout AI Phase 9 maintains strict functional boundaries:
| Concept | Engine / Responsibility | Decoupling Guarantee |
| :--- | :--- | :--- |
| **Eligibility** | `EligibilityChecker` | Ineligibility does not zero out relevance, but flags `INELIGIBLE` for clear user advisory. |
| **Relevance** | `MatchAnalyzer` | Evaluates user profile alignment and skill coverage without modifying database state. |
| **Similarity** | `SimilarityEngine` | Target-to-candidate comparison, completely independent of user preferences. |
| **Ranking** | `RankingService` | Phase 5 authoritative multi-factor ranking combining all signals deterministically. |

---

## 7. Security, RLS & Privacy Guarantees

1. **Row Level Security (RLS)**:
   - User preferences, explicit skills, and search history are protected by user-specific RLS policies.
   - User A cannot query or mutate User B's preferences or skills.
2. **No Sensitive Inferences**:
   - The engine strictly restricts signals to explicitly provided skills and opportunity interaction data.
   - Never infers demographic, political, socioeconomic, or personal characteristics.
3. **CSRF & Input Validation**:
   - All profile skill updates require valid CSRF tokens (`_user_csrf_token`).
   - Normalization sanitizes HTML tags and strips control characters.
4. **Authentication Integrity**:
   - `AdminSecurityManager` remains at module scope.
   - Anonymous users can browse public opportunity details and generic similarity without exposing personalized user data.

---

## 8. Known Limitations & Performance Bounds

- **Candidate Window**: Maximum 50 candidate records fetched during similarity stage 1 ensures sub-10ms response times on large tables.
- **Skill Vocabulary**: Vocabulary normalization is based on curated software/cybersecurity terms and rule-based sanitization rather than heavy third-party dictionaries.
