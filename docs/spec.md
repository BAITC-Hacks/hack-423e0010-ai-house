# Backend Specification — Explainable Contractor Recommendation Core

Normalized from: `hackathon dataset anonymized .csv`, `Архитектура платформы подбора подрядчиков.docx`, `Use-cases.xlsx`.
This document is the backend's source of truth. It only covers what is needed to build the system; it does not restate the source materials in full.

## 1. Product scope (this phase)

Given a search request, return up to 3 eligible event contractors for a single category, using **one** deterministic recommendation engine shared by the future structured form and the future AI chat assistant. The LLM/chat is out of scope for Phase 1 — the engine must be usable headless via HTTP so a chat layer can call it later without changes.

## 2. Request fields

Required:
- `city` (str)
- `event_date` (date, ISO `YYYY-MM-DD`)
- `event_format` (str, one of the dataset's `event_formats` values)
- `category` (str, one of the dataset's `categories` values)
- `budget_kzt` (int, > 0)

Optional:
- `duration_hours` (int, > 0)
- `language` (str)
- `preferences` (free text) — when non-empty (after `.strip()`), used for semantic ranking
  of the already-eligible pool (see §6.1). Never affects eligibility — hard filtering
  (§4) runs first and is identical with or without `preferences`.

## 3. Dataset shape (as observed in the CSV, 66 rows)

| column | notes |
|---|---|
| `id` | unique, e.g. `HK-39372` |
| `anon_name` | display name |
| `categories` | `\|`-delimited, a contractor may have several |
| `city` | single value per contractor (`Алматы`, `Астана`, `Зарубежье` observed) |
| `city_imputed` | bool, city was inferred during dataset prep — must be preserved/exposed |
| `synthetic` | bool, profile is synthetic — must be preserved/exposed |
| `price_from_kzt` | int, a **starting** price, not a guaranteed final price |
| `price_imputed` | bool, price was inferred — must be preserved/exposed |
| `event_formats` | `\|`-delimited |
| `languages` | `\|`-delimited |
| `max_hours` | int or empty. Empty means "duration not applicable to this category" (e.g. florist), **not** zero and **not** unlimited |
| `busy_dates` | `\|`-delimited ISO dates; the *only* signal for availability |
| `description` | free text; never overrides structured fields for hard filtering |

Calendar coverage in the current dataset: **2026-09-23 to 2026-12-31**. A `busy_dates` list only carries meaning inside this window — absence of a date in `busy_dates` outside the window does not imply availability.

## 4. Hard eligibility rules (in this order)

1. `contractor.city == request.city`
2. `request.category in contractor.categories`
3. `request.event_date not in contractor.busy_dates` (and `request.event_date` must fall inside the known calendar window — see §6)
4. `request.event_format in contractor.event_formats`
5. `contractor.price_from_kzt <= request.budget_kzt`
6. if `request.language` given: `request.language in contractor.languages`
7. if `request.duration_hours` given **and** `contractor.max_hours is not None`: `request.duration_hours <= contractor.max_hours`
   - if `contractor.max_hours is None`, duration is not applicable for that contractor/category and the check is skipped (does not exclude, does not require a match)

Rejection reasons (machine-readable, one contractor can carry several):
- `BUSY`
- `OVER_BUDGET`
- `FORMAT_UNSUPPORTED`
- `LANGUAGE_UNSUPPORTED`
- `DURATION_EXCEEDED`

City/category mismatch is not a "rejection reason" on a candidate — contractors outside the requested city/category are never candidates at all (see §5, `CATEGORY_ABSENT`).

## 5. Business outcomes

- **`MATCHED`** — 1 to 3 eligible contractors returned.
- **`CATEGORY_ABSENT`** — no contractor in `request.city` has `request.category` at all (before any other filter is applied).
- **`NO_MATCH`** — the city/category combination exists, but every candidate in it fails at least one hard filter.

Validation errors (bad input shape, e.g. missing required field, non-existent category/format spelling) and technical errors (5xx) are distinct from the three outcomes above and are surfaced as HTTP 4xx/5xx, not as a business status.

### Date outside calendar coverage

If `request.event_date` falls outside the dataset's known calendar window (min/max date present anywhere in `busy_dates` across the catalog), the API rejects the request explicitly as a validation error (HTTP 422) rather than silently treating the contractor as available. This is a deliberate Phase 1 limitation: availability is only known within the covered window.

## 6. Ranking

Hard filtering (§4) always runs first and is unaffected by `preferences`. Ranking of the
resulting eligible pool then depends on whether `preferences` was supplied:

**No `preferences`** (missing, `null`, empty, or whitespace-only after `.strip()`):
1. `price_from_kzt` ascending
2. `id` ascending (stable tie-break)

**Non-empty `preferences`** (Phase 2 — semantic ranking):
1. semantic similarity to `preferences`, descending
2. `price_from_kzt` ascending (tie-break)
3. `id` ascending (final stable tie-break)

Return at most 3 in both cases. Semantic ranking only ever reorders the eligible pool
computed by §4 — it can never make an ineligible contractor eligible, and never overrides
a hard rejection.

### 6.1 Semantic ranking (Phase 2)

- **Model**: `intfloat/multilingual-e5-base`, loaded via `sentence-transformers`, once per
  process (`app/api/deps.py:get_semantic_ranker`, `@lru_cache`, warmed at app startup via
  the FastAPI `lifespan` hook in `app/main.py`). Never reloaded per request.
- **Profile embeddings**: precomputed once for the whole catalog (66 contractors) when the
  ranker is constructed (`app/services/semantic.py:SemanticRanker.__init__`). Never
  recomputed per request — only the `preferences` query text is encoded per request.
- **Canonical semantic document** per contractor (`build_semantic_document`):
  ```
  <original full CSV description>. Категории: <sorted, comma-joined categories>. Форматы мероприятий: <sorted, comma-joined event_formats>.
  ```
  Category/format context is included for semantic disambiguation only — it never
  overrides structured-field filtering, which already happened in §4.
- **E5 retrieval convention**: `preferences` is encoded with the `"query: "` prefix;
  contractor documents are encoded with the `"passage: "` prefix (`QUERY_PREFIX` /
  `PASSAGE_PREFIX` in `app/services/semantic.py`, the single place these prefixes are
  applied). Both are L2-normalized so cosine similarity is a plain dot product, computed
  in-memory (no vector database — 66 profiles fits comfortably as a small matrix).
- **`semantic_score`**: a cosine similarity, not a probability and not a quality rating
  — never presented as a percentage. It is `null` on every returned contractor when
  `preferences` was absent/empty/whitespace-only, and a float otherwise.
- **Determinism / tie-break rule**: cosine similarities are rounded to 6 decimal places
  before being used as a sort key (`SIMILARITY_TIE_BREAK_DIGITS` in
  `app/services/recommendation.py`); scores within `1e-6` of each other are treated as
  equal and broken by `price_from_kzt` then `id`. The reported `semantic_score` itself is
  the unrounded value. The same request against the same dataset/model/profile vectors
  always produces the same order — no randomness, no LLM involved.

## 7. API surface (Phase 1)

- `GET /health` — liveness check.
- `POST /api/v1/recommend` — takes the request object from §2, returns:
  - `status`: `MATCHED` | `CATEGORY_ABSENT` | `NO_MATCH`
  - `results`: up to 3 contractor cards (id, name, category, city, price_from_kzt, event_formats, languages, max_hours, `synthetic`, `city_imputed`, `price_imputed`, `semantic_score`, `explanation`, `evidence` — see §9)
  - `rejected`: list of `{contractor_id, reasons: [...]}` for candidates that were in-scope (right city/category) but excluded — omitted/empty when status is `CATEGORY_ABSENT`
  - `rejection_summary`: `{reason: count}` aggregated over `rejected` — a quick machine-readable summary, most useful when `status` is `NO_MATCH`; empty dict when `rejected` is empty

No second semantic-search endpoint was added — `preferences` stays part of the existing
`RecommendRequest` schema and the same engine/endpoint handles both ranking modes.

## 8. Out of scope for this phase

PostgreSQL, LLM/chat integration, alternative-suggestion computation, multi-category
"event project" requests. The in-memory repository loaded from CSV stands in for
persistence. (Semantic ranking is in scope — see §6.1 — and deterministic,
evidence-grounded explanation generation is now in scope — see §9 — but the LLM chat
layer that will eventually *consume* the engine's output is not, and no wording in §9 is
ever produced by an LLM.)

## 9. Explanation and evidence generation (Phase 3)

Every returned contractor card carries `explanation` (a short Russian text, 1–2
sentences) and `evidence` (the structured facts backing it). Both are generated
deterministically — same inputs always produce the same output — and no LLM or network
call is involved in generating wording.

### 9.1 Grounding rule

Every statement in `explanation` must be traceable to one of:
- a structured field already verified by hard filtering (§4) or present on the request
  (availability on the requested date, matched event format, matched language when
  requested, requested vs. `max_hours` duration, `price_from_kzt` vs. `budget_kzt`);
- a verbatim excerpt from the contractor's own `description` field, selected as semantic
  evidence (§9.2).

Nothing is invented: no service, experience level, capacity, price guarantee, award, or
qualitative claim is asserted unless it is one of the above. `price_from_kzt` is always
phrased as a *starting* price ("стартовая цена ... укладывается в бюджет ..."), never as
final or guaranteed, per the hard rule in `CLAUDE.md`. When a description excerpt is used,
it is explicitly attributed to the contractor's own profile ("В описании подрядчик делает
акцент на: «...»") rather than restated as an independently verified fact — this applies
even when the profile text is itself a marketing claim.

### 9.2 Semantic evidence extraction

Implemented in `app/services/evidence.py` (`DescriptionEvidenceIndex`). Reuses the exact
same E5 encode function as `SemanticRanker` (`app/api/deps.py:get_encoder`, `@lru_cache`
singleton, shared by both — the model is loaded exactly once per process):

1. Each contractor's `description` is deterministically segmented once, at construction
   time, on sentence-ending punctuation/newlines (`segment_description`); segments shorter
   than 12 characters are dropped unless the description has no longer segment, in which
   case the whole description is kept as one segment.
2. Segment embeddings for the whole catalog are computed once (`passage:`-prefixed, same
   E5 convention as §6.1) at construction time — never recomputed per request.
3. Per request, the single query embedding already computed for ranking (§6.1) is reused
   (not re-encoded) to pick, per returned contractor, the description segment with the
   highest cosine similarity to the query (`DescriptionEvidenceIndex.best_segment`).
4. The selected excerpt is truncated to 220 characters and is always a verbatim substring
   of the contractor's `description` — never rephrased or summarized.

Evidence is only computed for the final ≤3 returned results (not the whole eligible
pool), and only when `preferences` was supplied — `evidence.semantic_excerpt` and
`evidence.semantic_score` are `null` on every card when `preferences` was
absent/empty/whitespace-only, matching the `semantic_score` rule in §6.1.

### 9.3 Response shape

```json
{
  "explanation": "Свободен 10 октября, формат «корпоратив», язык русский; рассчитан до 6 ч при запросе 6 ч; стартовая цена 500 000 ₸ укладывается в бюджет 1 000 000 ₸. В описании подрядчик делает акцент на: «Мой стиль — это сочетание интеллигентного юмора, четкой организации и высокого уровня ответственности.».",
  "evidence": {
    "available_on_date": true,
    "matched_event_format": "корпоратив",
    "matched_language": "русский",
    "requested_duration_hours": 6,
    "max_hours": 6,
    "price_from_kzt": 500000,
    "budget_kzt": 1000000,
    "semantic_excerpt": "Мой стиль — это сочетание интеллигентного юмора, четкой организации и высокого уровня ответственности.",
    "semantic_score": 0.8108800649642944
  }
}
```

No internal embeddings are exposed. `semantic_score`/`evidence.semantic_score` remain a
cosine similarity as defined in §6.1 — never presented as a probability or percentage.

### 9.4 Differentiation, not a filter checklist

`explanation` does not mechanically restate every matched filter (that would make same-city,
same-category, same-date-availability cards read identically). Instead it always includes:
price vs. budget (differs per contractor by construction) and, when applicable, the
requested-duration-vs-`max_hours` comparison and matched language — plus the
contractor-specific semantic excerpt when `preferences` was supplied. In practice, because
price and (when present) the semantic excerpt are contractor-specific, returned cards for
the same request do not produce interchangeable explanation text (verified by
`tests/test_explanation.py` and `tests/test_api.py`).

## 10. Semantic evaluation methodology (Phase 3)

`backend/evaluation/cases.py` holds ~12 curated `(structured filters, preferences)` cases
covering distinct real contractor styles found in the dataset (calm/business vs.
dance/entertainment hosting, documentary vs. aesthetic-emotional wedding photography,
premium vs. modern-minimalist decor, national ensembles, interactive photo booths, etc.).
Each case records a human-checked `rationale` citing the actual description text that
justifies the expectation.

Two expectation strengths are used deliberately, because the dataset does not support a
strict ground-truth ranking for every query:
- `expected_first` — used only where one candidate's own description text is unambiguously
  the best (or only) match; asserted strictly in `backend/tests/test_semantic_evaluation.py`
  and by `backend/evaluation/run.py` (non-zero exit on failure).
- `expected_in_top` — used where the dataset supports a plausible match among several
  candidates but not a provably exclusive ranking; checked as "at least one expected id
  in the top 3", reported as a warning (not a failure) if it doesn't hold.

Run standalone: `python -m evaluation.run` (prints every case's actual top-3 ids, scores,
and selected evidence). Re-run after any change to the embedding model, the canonical
semantic document (`build_semantic_document`), or the segmentation logic in
`app.services.evidence`.

### Limitations found

- **Negation is not reliably handled.** A query phrased as "серьёзный деловой стиль без
  развлекательной программы" (business style *without* an entertainment program) still
  ranked the dance/entertainment host (`HK-29829`) first over the explicitly
  business-styled host (`HK-88430`) — the opposite of the non-negated "серьёзный деловой
  стиль" query's result. This is a known general limitation of dense embedding similarity,
  not specific to this dataset; the evaluation case
  `business_forum_vs_dance_reversed` documents it as a soft (non-blocking) case rather than
  masking it.
- Short, generic descriptions (e.g. a one-sentence host profile) yield a single evidence
  segment regardless of query — there is nothing more specific in the profile to select.
- `semantic_score` is a raw cosine similarity, not a calibrated relevance/probability; two
  scores 0.81 and 0.80 are close in absolute terms but the ranking is still meaningful for
  ordering the same request's eligible pool (§6.1 tie-break at 1e-6 keeps ordering stable).

## 11. Model reproducibility (Phase 3)

Model identifier: `intfloat/multilingual-e5-base`, loaded via
`sentence_transformers.SentenceTransformer` in `app/services/semantic.py:default_encoder`.

- `EMBEDDING_MODEL_NAME` (env var, default `intfloat/multilingual-e5-base`) and
  `EMBEDDING_MODEL_REVISION` (env var, default unset) are read in `app/config.py` and
  passed through to `SentenceTransformer(model_name, revision=revision)`. Leaving
  `EMBEDDING_MODEL_REVISION` unset resolves the model repo's default branch on Hugging Face
  Hub at load time — reproducible only as long as that repo's default branch doesn't
  change; pin a specific revision (commit SHA or tag) via the env var for deployments that
  need bit-for-bit reproducibility across time.
- Model weights are **not** vendored into git. A fresh environment needs network access to
  the Hugging Face Hub on first run to download and cache the model (subsequent runs use
  the local cache, e.g. `~/.cache/huggingface`); `HF_HUB_OFFLINE` is not set by this
  project, so an offline deployment must either pre-warm that cache or set
  `HF_HUB_OFFLINE=1` with the cache already populated.

## 9. Ambiguities found in source material (resolved for Phase 1)

- The architecture doc's proposed API surface (`/selection-requests`, `/chat/messages`, etc.) describes the eventual multi-endpoint, stateful-request architecture. The task brief for this phase explicitly specifies `POST /api/v1/recommend` as a single stateless endpoint. Phase 1 implements the brief's simpler contract; the richer request-versioning API is deferred (see `TASKS.md`).
- The dataset has one contractor in city `Зарубежье` (lit. "abroad") — treated like any other city value, no special-casing.
- `preferences` free text was inert in Phase 1 (accepted, unused). Phase 2 makes it drive
  semantic ranking of the eligible pool only — see §6.1. It still never affects eligibility.
