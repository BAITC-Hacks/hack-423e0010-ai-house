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

## Phase 3 — explainability + semantic evaluation (this session)

- [x] Curated semantic-ranking evaluation harness against the real dataset (`backend/evaluation/cases.py`, `backend/evaluation/run.py`, `backend/tests/test_semantic_evaluation.py`) — ~12 cases across host style, photography style, decor style, national ensembles, photo booths
- [x] Deterministic description-segment evidence extraction reusing the existing E5 model/encoder, precomputed once (`app/services/evidence.py`)
- [x] Deterministic explanation generation, grounded only in structured facts + selected evidence, differentiated per contractor (`app/services/explanation.py`)
- [x] `ContractorCard.explanation` / `ContractorCard.evidence` (`RecommendationEvidence`) added to the response schema; `RecommendResponse.rejection_summary` added
- [x] Tests: explanation presence/grounding, evidence-from-description, evidence null without preferences, determinism, differentiation across contractors, price-as-starting-price phrasing, marketing-claim attribution, eligibility unaffected by evidence extraction, no-LLM/no-network requirement
- [x] Model reproducibility: `EMBEDDING_MODEL_NAME`/`EMBEDDING_MODEL_REVISION` env-configurable, documented in `docs/spec.md` §11
- [x] `docs/spec.md` §9–§11, `PROGRESS.md` updated

## Phase 4 — chat assistant (future, not started)

- [ ] Stateful selection-request object (create/patch), matching the docx's `/selection-requests` API shape
- [ ] Bounded toolset: `get_catalog_options`, `update_request`, `recommend`, `get_profile`, `compare_candidates`, `suggest_alternatives`
- [ ] Chat endpoint calling the same recommendation engine — LLM never picks final contractors and never generates `explanation` wording (that stays deterministic per Phase 3)

## Phase 5 — persistence & infra (future, not started)

- [ ] PostgreSQL-backed catalog/availability instead of in-memory CSV load
- [ ] Dataset/model/version tracking for reproducibility (per docx §5, §9)
- [ ] Alternative-suggestion computation (nearby dates / minimum budget) — must be computed by re-running real filters, never invented
