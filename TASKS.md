# Tasks

## Phase 1 — deterministic recommendation core (this session)

- [x] Inspect source materials (CSV, architecture docx, use-cases xlsx)
- [x] Write `docs/spec.md`
- [x] Backend project scaffold (`backend/pyproject.toml`, package layout)
- [x] Domain models (`Contractor`, enums, rejection reasons)
- [x] CSV loader/normalizer + in-memory repository
- [x] Pydantic v2 request/response schemas
- [x] Eligibility filtering service (hard rules, rejection reasons)
- [x] Deterministic ranking (price asc, id asc), max 3 results
- [x] Business outcome resolution (`MATCHED` / `CATEGORY_ABSENT` / `NO_MATCH`)
- [x] `GET /health`
- [x] `POST /api/v1/recommend`
- [x] Test suite covering all `required_tests` scenarios
- [x] Run full suite, run one real request through `TestClient`
- [x] `PROGRESS.md` updated

## Phase 2 — semantic ranking (this session)

- [x] Precompute description embeddings, in-memory similarity (per architecture doc — no vector DB for this dataset size)
- [x] Replace primary ranking criterion with preference match (semantic similarity), keep price/id as tie-break
- [x] `intfloat/multilingual-e5-base` via `sentence-transformers`, loaded once (app lifespan), profile embeddings precomputed once per catalog
- [x] `semantic_score` surfaced on each result card only when `preferences` was used
- [x] Tests: trigger/no-trigger, eligible-only scoring, busy/over-budget contractors never returned despite strong semantic match, determinism, max 3, structured-field override, no-recompute-per-request
- [ ] Extract verifiable "features" from descriptions with supporting text spans (deferred — not needed for ranking, would support future explanation generation)
- [ ] Explanation generation from verified facts only (template-based; LLM optional and must degrade gracefully) — deferred to a later phase

## Phase 3 — chat assistant (future, not started)

- [ ] Stateful selection-request object (create/patch), matching the docx's `/selection-requests` API shape
- [ ] Bounded toolset: `get_catalog_options`, `update_request`, `recommend`, `get_profile`, `compare_candidates`, `suggest_alternatives`
- [ ] Chat endpoint calling the same recommendation engine — LLM never picks final contractors

## Phase 4 — persistence & infra (future, not started)

- [ ] PostgreSQL-backed catalog/availability instead of in-memory CSV load
- [ ] Dataset/model/version tracking for reproducibility (per docx §5, §9)
- [ ] Alternative-suggestion computation (nearby dates / minimum budget) — must be computed by re-running real filters, never invented
