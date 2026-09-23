# Progress

## Phase 1 — implemented and verified (2026-09-23)

Deterministic recommendation core is complete per `docs/spec.md` / `TASKS.md`.

**Implemented:**
- CSV loading/normalization (`backend/app/repositories/catalog.py`) — parses `|`-delimited fields, booleans, dates, and `max_hours` empty → `None`. In-memory `CatalogRepository`.
- Domain model `Contractor` (`backend/app/domain/models.py`), rejection-reason and status enums (`backend/app/domain/enums.py`).
- Eligibility + ranking engine (`backend/app/services/recommendation.py`), framework-independent of FastAPI/Pydantic — usable by a future chat layer without changes.
- Pydantic v2 request/response schemas (`backend/app/schemas/recommend.py`).
- `GET /health`, `POST /api/v1/recommend` (`backend/app/api/routes.py`, `app/main.py`).
- 20 tests (`backend/tests/`): unit tests against constructed fixtures for exact rule coverage, integration tests against the real CSV via `TestClient`.

**Verified:**
- `pytest` — 20/20 passing.
- Manual `TestClient` run of the docx's example payload (Алматы / Ведущий / корпоратив / 1M KZT / 6h / русский) returns `MATCHED` with 3 ranked cards and 6 rejected candidates with correct reasons, matching the dataset by hand-check.
- `uvicorn app.main:app` boots and serves real HTTP `GET /health` and `GET /docs` (200 OK).

**Requirement checklist from the brief — all covered by tests:**
- busy contractor never returned — `test_busy_contractor_never_returned`
- over-budget contractor never returned — `test_over_budget_contractor_never_returned`
- unsupported format excludes — `test_unsupported_event_format_excludes_contractor`
- language filtering when supplied / ignored when not — `test_language_filtering_applies_when_language_specified`, `test_language_ignored_when_not_specified`
- duration filtering — `test_duration_filtering_excludes_contractor_with_lower_max_hours`, `test_duration_within_max_hours_is_eligible`
- `max_hours = null` handled (not applicable, not zero, not unlimited) — `test_null_max_hours_is_not_applicable_and_never_excludes`, `test_null_max_hours_does_not_get_treated_as_zero`
- max 3 results — `test_maximum_result_size_is_three`, `test_result_never_exceeds_three`
- determinism (same request → same IDs/order) — `test_same_request_produces_same_ids_in_same_order`
- date change → different results — `test_changing_only_date_can_change_results_due_to_availability`
- `CATEGORY_ABSENT` vs `NO_MATCH` distinguishable — `test_category_absent_vs_no_match_are_distinguishable` (unit), `test_category_absent_and_no_match_are_distinguishable` (real data)
- `synthetic` / `city_imputed` / `price_imputed` survive to the API response — `test_recommend_matched_and_metadata_survives`
- invalid date outside calendar coverage handled explicitly (422) — `test_invalid_date_outside_calendar_window_is_rejected`

## Phase 2 — implemented and verified (2026-09-23)

Deterministic semantic ranking is complete per `docs/spec.md` §6/§6.1 and `TASKS.md`. The
hard-filtering engine remains the sole source of eligibility; semantic ranking only ever
reorders the already-eligible pool.

**Implemented:**
- `backend/app/services/semantic.py` — `SemanticRanker` (precomputes catalog profile
  embeddings once at construction, scores eligible candidates against a `preferences`
  query per request), `build_semantic_document` (canonical per-contractor text), E5
  `query:`/`passage:` prefix constants, `ScoredContractor`.
- `backend/app/services/recommendation.py` — `recommend()` now takes an optional
  `SemanticRanker`; ranks by semantic similarity desc / price asc / id asc when
  `preferences` is non-empty, else keeps Phase 1 price/id ranking. Results are
  `ScoredContractor` (contractor + `semantic_score: float | None`).
- `backend/app/api/deps.py` — `get_semantic_ranker()`, `@lru_cache` singleton.
- `backend/app/main.py` — FastAPI `lifespan` warms the ranker (model load + catalog
  embeddings) once at startup instead of on the first request.
- `backend/app/schemas/recommend.py` — `ContractorCard.semantic_score: float | None`.
- `backend/pyproject.toml` — added `sentence-transformers` dependency.
- 17 new tests (`backend/tests/test_semantic_ranking.py`, plus additions to
  `test_api.py`): fake-encoder tests for pure ranking logic/determinism/call-counting,
  plus real-model tests (session-scoped fixtures) for genuine semantic behavior and
  end-to-end API checks.

**Verified:**
- `pytest` — 37/37 passing (20 original + 17 new).
- Real requests, same hard filters (Алматы/Ведущий/корпоратив/2026-10-10/budget 700k KZT,
  eligible pool = {HK-88430, HK-29829}), different `preferences`:
  - `"спокойная деловая интеллигентная подача, корпоративный стиль"` → `HK-88430` first
    (0.8109 vs 0.8029)
  - `"яркое шоу с танцами и развлечениями"` → `HK-29829` first (0.8172 vs 0.7739)
  - Same eligible IDs in both cases, order flips — semantic layer never touches eligibility.
- Repeated identical requests (same preferences) return identical IDs and identical
  `semantic_score` values.
- Latency after warm-up (model load + catalog embedding, ~14s one-time cost): ~11.5 ms per
  `recommend()` call (20-call average), dominated by encoding the single query string.

**Known limitations:**
- First request after process start pays the one-time model-load/embed cost unless the
  `lifespan` warm-up has already run (it has, for `uvicorn`; not for a bare `TestClient()`
  used outside `with`, where the `@lru_cache` dependency still loads lazily on first call).
- `HF_HUB_OFFLINE` is not set, so the app checks Hugging Face Hub for the pinned model on
  first load if not already cached; no network access needed once cached locally.

## Not started

Phases 3–4 in `TASKS.md` (chat assistant, PostgreSQL/persistence). Not touched this session.
