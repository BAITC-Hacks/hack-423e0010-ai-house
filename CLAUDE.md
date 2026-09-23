# CLAUDE.md

Guidance for working in this repository.

## What this is

Backend for an explainable event-contractor recommendation platform (hackathon project, Kazakhstan). Phase 1 delivers a deterministic, rule-based recommendation core — no LLM, no semantic search, no database yet. See `docs/spec.md` for the normalized requirements and `TASKS.md` for phase breakdown.

## Source of truth

- `docs/spec.md` — normalized backend requirements (read this before changing eligibility/ranking rules)
- `docs/hackathon dataset anonymized .csv` — the dataset; treat its structured fields as authoritative over `description` free text
- `docs/Архитектура платформы подбора подрядчиков.docx` — original architecture proposal (Russian). Phase 1 implements a subset of it per the task brief; do not implement its later-phase API surface early.

## Core invariant

The structured form and the future chat assistant must call the **same** recommendation engine (`backend/app/services/recommendation.py`). Never let an LLM choose final contractors — it may only consume the engine's output.

## Hard rules (do not relax silently)

- A busy contractor (per `busy_dates`) must never be returned, ever.
- `max_hours = null` means duration is not applicable to that contractor — not zero, not unlimited.
- `price_from_kzt` is a starting price; never present it as a final/guaranteed price.
- `description` text must never override structured-field filtering.
- Dates outside the dataset's calendar coverage window are rejected explicitly, not silently treated as available.
- Preserve and surface `synthetic`, `city_imputed`, `price_imputed` through the API.

## Running

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate   # first time
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

## Conventions

- Python 3.11+, FastAPI, Pydantic v2, pytest.
- Keep dependencies minimal — do not add a frontend, LangChain/LangGraph/CrewAI, a vector DB, Redis, Kafka, Kubernetes, or LLM/embedding integrations until the corresponding phase in `TASKS.md` is actually started.
- No `BaseService`/`BaseRepository` abstractions unless a second concrete implementation actually needs them.
- Validate at system boundaries (API request schemas); trust internal domain code.
