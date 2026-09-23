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

## Phase 3 — explainability + semantic evaluation — implemented and verified (2026-09-23)

Deterministic evidence extraction and explanation generation, plus a curated semantic
evaluation harness, per `docs/spec.md` §9–§11 and `TASKS.md`. No LLM is used anywhere in
this phase; every explanation sentence is traceable to a structured field or a verbatim
description excerpt.

**Implemented:**
- `backend/app/domain/evidence.py` — `EvidenceMatch(excerpt, score)`.
- `backend/app/services/evidence.py` — `DescriptionEvidenceIndex`: deterministic
  sentence/newline segmentation (`segment_description`), segment embeddings for the whole
  catalog precomputed once at construction (reuses the same E5 encode function as
  `SemanticRanker`, never a second model load), `best_segment(query_embedding, contractor)`
  selects the highest-cosine-similarity segment per contractor from an already-encoded
  query vector (no extra encode call per request).
- `backend/app/services/explanation.py` — `build_explanation(query, scored)`: deterministic
  1–2 sentence Russian explanation combining structured facts (availability, format,
  language when requested, duration vs. `max_hours`, `price_from_kzt` vs. `budget_kzt`
  phrased as a starting price) with the selected semantic evidence excerpt when
  `preferences` was supplied, attributed as "В описании подрядчик делает акцент на: «...»"
  rather than asserted as verified fact.
- `backend/app/services/recommendation.py` — `recommend()` takes an optional
  `evidence_index`; the query embedding computed for ranking is reused for evidence
  selection on the final ≤3 results only (still exactly one encode call per
  preferences-bearing request). `ScoredContractor.evidence: EvidenceMatch | None`.
- `backend/app/services/semantic.py` — `SemanticRanker.encode_query` /
  `score_with_embedding` split out from `score()` so the query embedding can be shared
  between ranking and evidence extraction; `default_encoder` now accepts a `revision`.
- `backend/app/api/deps.py` — `get_encoder()` (`@lru_cache`), shared by
  `get_semantic_ranker()` and the new `get_evidence_index()` so the model loads exactly
  once. `app/main.py` lifespan warms both.
- `backend/app/schemas/recommend.py` — `RecommendationEvidence`,
  `ContractorCard.explanation` / `.evidence`, `RecommendResponse.rejection_summary`
  (reason → count, aggregated from `rejected`).
- `backend/app/config.py` — `EMBEDDING_MODEL_NAME` / `EMBEDDING_MODEL_REVISION` now
  environment-configurable (see `docs/spec.md` §11 for reproducibility notes).
- `backend/evaluation/cases.py` — 12 curated semantic-evaluation cases against the real
  dataset (host style, wedding-photography style, decor style, national ensembles,
  interactive photo booths, live-band sound, corporate gifts), each with a rationale citing
  the actual description text and a strict (`expected_first`) or soft (`expected_in_top`)
  expectation. `backend/evaluation/run.py` — standalone runner
  (`python -m evaluation.run`), non-zero exit on a strict failure.
- 36 new tests: `backend/tests/test_explanation.py` (segmentation, evidence-selection,
  grounding rules, determinism, cross-contractor differentiation, real-model integration),
  additions to `backend/tests/test_api.py` (schema fields, rejection summary, identical
  explanation on repeat), `backend/tests/test_semantic_evaluation.py` (parametrized over
  the evaluation cases).

**Verified:**
- `pytest` — 73/73 passing (37 Phase 1/2 + 36 new).
- `python -m evaluation.run` — 12/12 cases, 0 strict failures, 0 soft failures (one case
  documents a known model limitation — see below — without being forced to pass strictly).
- Real 3-card example (Алматы / Ведущий / корпоратив / 2026-10-10 / budget 1,000,000 /
  duration 6h / язык русский / preferences "спокойная деловая интеллигентная подача,
  корпоративный стиль"): `HK-88430`, `HK-77838`, `HK-29829` returned with three distinct
  explanation strings (different prices, different `max_hours`, different real evidence
  excerpts from each profile's own description).
- Repeated identical requests (with and without `preferences`) return identical
  `results` order, `semantic_score` values, and `explanation` text.
- Evidence/explanation never changes eligibility or ranking order versus the same request
  run without an evidence index — verified in
  `test_busy_and_ineligible_contractors_still_excluded_with_evidence_enabled`.
- Warm-request latency after explainability: ~13–16 ms/call (`TestClient`, 20–30 call
  average), up from ~11.5 ms in Phase 2 — still dominated by the single per-request query
  encode call.

**Known limitations found by the evaluation harness:**
- Negation is not reliably handled by the E5 model: "серьёзный деловой стиль без
  развлекательной программы" still ranked the dance/entertainment host first over the
  explicitly business-styled host — the opposite of the non-negated query's result. Recorded
  as a soft (non-blocking) evaluation case rather than masked; see `docs/spec.md` §10.
- Short, generic contractor descriptions yield the same single evidence segment
  regardless of query — there's nothing more specific in the profile to select.

## Phase 4 — chat assistant + minimal demo UI — implemented and verified (2026-09-23)

`POST /api/v1/chat` and a static browser UI, per the hackathon-final-stage brief and
`TASKS.md`. The recommendation engine (`app/services/recommendation.py`) is unchanged;
the chat layer only translates free text into a structured patch and calls the same
engine `/api/v1/recommend` already used.

**Implemented:**
- `backend/app/services/llm_client.py` — `LLMIntent` (`action`/`patch`/`message`),
  `LLMParseError`/`LLMUnavailableError`, `build_system_prompt` (injects the real catalog's
  cities/categories/event formats/languages so the LLM never invents an unsupported
  value), `openai_complete_factory` — one `chat.completions.create` call via the `openai`
  SDK against an OpenAI-compatible endpoint (`LLM_BASE_URL`), JSON-only response parsed
  and validated, no tool-calling loop, no agent framework.
- `backend/app/services/chat.py` — `run_chat` (framework-independent, like
  `recommendation.py`): merges the LLM's patch onto `current_search`, drops any
  unparsable/unknown field rather than failing, checks the 5 required fields
  (city/event_date/event_format/category/budget_kzt), returns `CLARIFY` with a concise
  Russian question when any are missing (never guesses them), checks the calendar window
  before calling the engine, and otherwise calls `app.services.recommendation.recommend` +
  the shared `build_recommend_response` — identical code path to `/api/v1/recommend`.
  No LLM configured, or the LLM call raising `LLMError`, both degrade to a plain `ANSWER`
  message (current search preserved, `recommendation: null`) — never a crash, never a
  fabricated `NO_MATCH`.
- `backend/app/services/response_builder.py` — `_to_card`/`build_recommend_response`
  extracted from `api/routes.py` so `/api/v1/recommend` and `/api/v1/chat` build the exact
  same `RecommendResponse` from a `RecommendResult`; `/api/v1/recommend`'s behavior is
  byte-for-byte unchanged (same 73 pre-existing tests pass unmodified).
- `backend/app/schemas/chat.py` — `SearchState` (all fields optional), `ChatRequest`,
  `ChatResponse`. `backend/app/schemas/recommend.py` — `CatalogOptions`.
- `backend/app/domain/enums.py` — `ChatAction` (`SEARCH`/`UPDATE_SEARCH`/`CLARIFY`/`ANSWER`).
- `backend/app/api/deps.py` — `get_llm_complete_fn()` (`@lru_cache`; returns `None` when
  `LLM_API_KEY` is unset — dependency-injectable/overridable in tests), `catalog_options()`.
- `backend/app/api/routes.py` — `POST /api/v1/chat`, `GET /api/v1/catalog-options`.
- `backend/app/config.py` — `LLM_API_KEY`/`LLM_MODEL`/`LLM_BASE_URL`
  (`.env.example`, provider-agnostic OpenAI-compatible names); `load_dotenv()` so
  `backend/.env` is picked up automatically by `uvicorn app.main:app` with no extra flags
  (an env var already set in the shell still wins). `REQUIRED_SEARCH_FIELDS`.
- `backend/app/static/` — dependency-free HTML/CSS/vanilla-JS demo UI (`index.html`,
  `app.js`, `styles.css`), served by FastAPI itself via `StaticFiles(html=True)` mounted
  at `/` (mounted after the API router, so it never shadows `/health`,
  `/api/v1/*`, `/docs`, `/openapi.json`). Search form (dropdowns populated from
  `GET /api/v1/catalog-options`, so it can never submit an unsupported value), up-to-3
  result cards showing name/categories/city/starting price/explanation/semantic
  relevance-labeled score/synthetic & imputed badges, visibly distinct MATCHED /
  CATEGORY_ABSENT / NO_MATCH (+ rejection-reason summary) states, and a chat panel that
  posts to `/api/v1/chat` and syncs the returned `search` back into the form fields and
  the returned `recommendation` into the cards.
- `pyproject.toml` — added `openai`, `python-dotenv`.
- 12 new tests (`backend/tests/test_chat.py`): full-search extraction, date-only /
  budget-only / preferences-only follow-ups each change only that field, missing-required
  → `CLARIFY`, explicit LLM `CLARIFY` honored even with a full patch, malformed LLM output
  handled safely, LLM transport failure never becomes `NO_MATCH`, unconfigured-LLM message,
  chat and a direct `recommend()` call agree on identical result IDs for the same query,
  plus 2 `TestClient`-level checks (unconfigured LLM via the real route, mocked LLM via
  `app.dependency_overrides[get_llm_complete_fn]`). All mock the LLM — no network/paid
  API calls in the suite.

**Verified:**
- `pytest` — 85/85 passing (73 Phase 1–3 unchanged + 12 new).
- `python -m evaluation.run` — 12/12 semantic cases, 0 strict/soft failures (unchanged).
- `GET /health`, `GET /docs`, `GET /` (200, serves `index.html`), `GET /app.js`,
  `GET /styles.css`, `GET /api/v1/catalog-options` all verified live via `uvicorn`.
- `POST /api/v1/recommend` manually re-verified for all three states: MATCHED (Алматы /
  Ведущий / корпоратив / 2026-10-10 / 1,000,000 KZT → 3 cards with explanations),
  CATEGORY_ABSENT (Астана / Ресторан), NO_MATCH (Алматы / Ведущий / budget 100,000, with
  non-empty `rejection_summary`).
- Chat without `LLM_API_KEY` set: `/api/v1/chat` returns `action: "ANSWER"`,
  `"AI-помощник не настроен. Обычный поиск продолжает работать."`, `recommendation: null`
  — confirmed the structured search stays fully functional either way.
- **Real 3-turn live demo**, run against the user-supplied `LLM_API_KEY`/`LLM_MODEL`/
  `LLM_BASE_URL` (OpenAI-compatible endpoint) in `backend/.env`:
  1. *"Нужен ведущий в Алматы на корпоратив 10 октября 2026, бюджет до 700 тысяч. Хочется
     спокойной интеллигентной подачи."* → `action=SEARCH`, full search extracted in one
     turn, `MATCHED` with 2 cards (`HK-29829`, `HK-88430`).
  2. *"А теперь хочется кого-нибудь повеселее, с танцами и развлечениями"* →
     `action=UPDATE_SEARCH`, only `preferences` changed (city/date/format/category/budget
     all identical to turn 1), semantic scores recomputed, still `MATCHED`.
  3. *"А теперь 17 октября"* → `action=UPDATE_SEARCH`, only `event_date` changed to
     `2026-10-17`, availability recalculated → `NO_MATCH` (verified identical to calling
     `POST /api/v1/recommend` directly with the same fields — chat never diverges from the
     engine).
  - Also verified the `CLARIFY` path live: *"Нужен фотограф на свадьбу"* →
    `missing_fields: ["city", "event_date", "budget_kzt"]`, a concise Russian question,
    no invented values.
- Found and fixed one real integration bug during the live run: the configured model
  rejected the `max_tokens` parameter (`"Unsupported parameter: 'max_tokens' ... Use
  'max_completion_tokens' instead"`) — switched `llm_client.py` to
  `max_completion_tokens`, confirmed working against the same live endpoint before
  re-running the 3-turn demo above.

**Provider note:** the brief's example env names (`LLM_API_KEY`/`LLM_MODEL`/
`LLM_BASE_URL`) are provider-agnostic by design; the actual `backend/.env` supplied for
this session pointed at an OpenAI-compatible endpoint, so `llm_client.py` implements the
OpenAI Chat Completions API (via the `openai` SDK) rather than Anthropic.

## Not started

Phase 5 (PostgreSQL/persistence, alternative-suggestion computation) in `TASKS.md`. Not
touched this session — out of scope per the deadline rules (no PostgreSQL/Redis/auth/
persistent chat history).
