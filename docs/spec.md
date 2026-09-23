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
- `preferences` (free text) — **stored/accepted but not used for filtering or ranking in Phase 1** (semantic ranking is a later phase; free text must never affect eligibility).

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

## 6. Ranking (Phase 1 only — temporary)

Eligible candidates are ordered by:
1. `price_from_kzt` ascending
2. `id` ascending (stable tie-break)

Return at most 3. No semantic/preference ranking yet — `preferences` free text is accepted by the API but not used to rank or filter in this phase.

## 7. API surface (Phase 1)

- `GET /health` — liveness check.
- `POST /api/v1/recommend` — takes the request object from §2, returns:
  - `status`: `MATCHED` | `CATEGORY_ABSENT` | `NO_MATCH`
  - `results`: up to 3 contractor cards (id, name, category, city, price_from_kzt, event_formats, languages, max_hours, `synthetic`, `city_imputed`, `price_imputed`)
  - `rejected`: list of `{contractor_id, reasons: [...]}` for candidates that were in-scope (right city/category) but excluded — omitted/empty when status is `CATEGORY_ABSENT`

## 8. Out of scope for this phase

PostgreSQL, embeddings, LLM/chat integration, semantic ranking, explanation generation from free text, alternative-suggestion computation, multi-category "event project" requests. The in-memory repository loaded from CSV stands in for persistence.

## 9. Ambiguities found in source material (resolved for Phase 1)

- The architecture doc's proposed API surface (`/selection-requests`, `/chat/messages`, etc.) describes the eventual multi-endpoint, stateful-request architecture. The task brief for this phase explicitly specifies `POST /api/v1/recommend` as a single stateless endpoint. Phase 1 implements the brief's simpler contract; the richer request-versioning API is deferred (see `TASKS.md`).
- The dataset has one contractor in city `Зарубежье` (lit. "abroad") — treated like any other city value, no special-casing.
- `preferences` free text is part of the request schema (per the brief and docx example payload) but is inert in Phase 1 — accepted and echoed nowhere, used nowhere, documented here so it isn't mistaken for a bug.
