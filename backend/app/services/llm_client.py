"""Thin LLM wrapper for `POST /api/v1/chat`.

The LLM is used for exactly one thing: turning a free-text user message
(plus the current search state) into a small structured intent — an
`action` and a `patch` of search fields to apply. It never sees, selects,
ranks, or describes contractors; `app.services.chat` applies the patch and
calls the existing deterministic `app.services.recommendation.recommend`
for everything downstream.

No agent framework, no tool-calling loop — one request, one JSON response.
"""

import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.domain.enums import ChatAction

ALLOWED_PATCH_FIELDS = (
    "city",
    "event_date",
    "event_format",
    "category",
    "budget_kzt",
    "duration_hours",
    "language",
    "preferences",
)


class LLMIntent(BaseModel):
    action: ChatAction
    patch: dict[str, Any] = {}
    message: str | None = None


class LLMError(Exception):
    """Base class for recoverable chat-LLM failures."""


class LLMParseError(LLMError):
    """The LLM responded, but not with valid structured intent JSON."""


class LLMUnavailableError(LLMError):
    """The LLM call itself failed (network/API error)."""


LLMCompleteFn = Callable[[str, dict[str, Any]], LLMIntent]


def build_system_prompt(catalog_options: dict[str, list[str]]) -> str:
    options_text = "\n".join(
        f"- {field}: {', '.join(values)}" for field, values in catalog_options.items()
    )
    return f"""You are a structured intent parser for an event-contractor search assistant.
You NEVER choose, rank, or describe contractors, and you NEVER invent facts about
availability, price, or contractors — a separate deterministic engine does that.
Your only job: read the user's message and the current search state, and return
ONE JSON object describing how to update the search, in Russian for any text
shown to the user.

Known catalog values (use these exact strings when a field matches one of them;
if the user's wording doesn't clearly match, ask instead of guessing):
{options_text}

Respond with ONLY a JSON object (no markdown fences, no prose) of this shape:
{{
  "action": "SEARCH" | "UPDATE_SEARCH" | "CLARIFY" | "ANSWER",
  "patch": {{"<field>": <value>, ...}},
  "message": "<short Russian reply to show the user, or null>"
}}

Rules:
- "patch" may only contain these fields: {", ".join(ALLOWED_PATCH_FIELDS)}.
- Only include a field in "patch" if the user's message actually specifies or
  changes it. Never repeat unchanged fields, never invent values.
- "event_date" must be an ISO date "YYYY-MM-DD" if included.
- "budget_kzt" and "duration_hours" must be integers if included.
- Use "SEARCH" for a first/complete search request, "UPDATE_SEARCH" for a
  follow-up that changes one or more fields of an existing search.
- Use "CLARIFY" when required fields (city, event_date, event_format,
  category, budget_kzt) are still missing after applying your patch — put a
  concise Russian question in "message" naming what's missing. Do not guess
  missing mandatory fields.
- Use "ANSWER" for a general question/remark that isn't a search change —
  put a short factual Russian reply in "message", and do not describe or
  invent specific contractors.
"""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def parse_llm_response(text: str) -> LLMIntent:
    try:
        data = _extract_json(text)
        return LLMIntent.model_validate(data)
    except (json.JSONDecodeError, ValidationError, AttributeError, TypeError) as exc:
        raise LLMParseError(str(exc)) from exc


def openai_complete_factory(
    api_key: str,
    model: str,
    base_url: str | None,
    catalog_options: dict[str, list[str]],
) -> LLMCompleteFn:
    """Builds an `LLMCompleteFn` backed by an OpenAI-compatible Chat
    Completions API (`openai` SDK; `base_url` may point at a compatible
    gateway instead of api.openai.com).

    Import is local so the dependency is only touched when a chat LLM is
    actually configured (`LLM_API_KEY` set), matching the pattern already
    used for the (heavier) embedding model in `app.services.semantic`.
    """
    from openai import OpenAI

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    system_prompt = build_system_prompt(catalog_options)

    def complete(message: str, current_search: dict[str, Any]) -> LLMIntent:
        user_content = json.dumps(
            {"current_search": current_search, "message": message},
            ensure_ascii=False,
            default=str,
        )
        try:
            response = client.chat.completions.create(
                model=model,
                max_completion_tokens=512,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - any transport/API failure
            raise LLMUnavailableError(str(exc)) from exc

        text = (response.choices[0].message.content or "").strip()
        return parse_llm_response(text)

    return complete
