"""Chat orchestration for `POST /api/v1/chat`.

Framework-independent (no FastAPI import here), same spirit as
`app.services.recommendation`: the LLM only produces a structured intent
(action + patch of search fields); this module validates and applies that
patch, then calls the *same* `app.services.recommendation.recommend` used by
the structured `/api/v1/recommend` endpoint. The LLM never sees contractor
data and never produces the final recommendation or its explanations.
"""

from datetime import date
from typing import Any

from app.config import REQUIRED_SEARCH_FIELDS
from app.domain.enums import ChatAction
from app.repositories.catalog import CatalogRepository
from app.schemas.chat import ChatRequest, ChatResponse, SearchState
from app.schemas.recommend import RecommendResponse
from app.services.evidence import DescriptionEvidenceIndex
from app.services.llm_client import ALLOWED_PATCH_FIELDS, LLMCompleteFn, LLMError
from app.services.recommendation import RecommendQuery, recommend
from app.services.response_builder import build_recommend_response
from app.services.semantic import SemanticRanker

NOT_CONFIGURED_MESSAGE = "AI-помощник не настроен. Обычный поиск продолжает работать."
LLM_FAILURE_MESSAGE = (
    "Не удалось обработать сообщение через AI-помощника. Попробуйте "
    "переформулировать запрос или используйте обычную форму поиска."
)

_INT_FIELDS = {"budget_kzt", "duration_hours"}

_FIELD_LABELS = {
    "city": "город",
    "event_date": "дата мероприятия",
    "event_format": "формат мероприятия",
    "category": "категория подрядчика",
    "budget_kzt": "бюджет",
}


def _missing_fields(merged: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_SEARCH_FIELDS if not merged.get(field)]


def _sanitize_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """Keeps only known fields with values that parse to the right type.
    Anything else (unknown field, wrong type, unparsable date) is dropped
    rather than raising — a malformed LLM patch must never crash the
    endpoint, only leave that field unchanged / still missing.
    """
    clean: dict[str, Any] = {}
    for field in ALLOWED_PATCH_FIELDS:
        if field not in patch or patch[field] is None:
            continue
        value = patch[field]
        try:
            if field == "event_date":
                value = date.fromisoformat(str(value))
            elif field in _INT_FIELDS:
                value = int(value)
            else:
                value = str(value).strip()
                if not value:
                    continue
        except (TypeError, ValueError):
            continue
        clean[field] = value
    return clean


def _default_clarify_message(missing: list[str]) -> str:
    named = ", ".join(_FIELD_LABELS.get(field, field) for field in missing)
    return f"Уточните, пожалуйста: {named}."


def _default_result_message(search: SearchState, response: RecommendResponse) -> str:
    if response.status == "MATCHED":
        n = len(response.results)
        return f"Нашёл подходящих вариантов: {n}."
    if response.status == "CATEGORY_ABSENT":
        return f"Категория «{search.category}» отсутствует в городе «{search.city}»."
    return "Подходящих вариантов по заданным условиям не найдено."


def _clarify_response(assistant_message: str, search: SearchState) -> ChatResponse:
    return ChatResponse(
        action=ChatAction.CLARIFY,
        assistant_message=assistant_message,
        search=search,
        missing_fields=_missing_fields(search.model_dump()),
        recommendation=None,
    )


def run_chat(
    request: ChatRequest,
    repo: CatalogRepository,
    ranker: SemanticRanker,
    evidence_index: DescriptionEvidenceIndex,
    llm_complete: LLMCompleteFn | None,
) -> ChatResponse:
    current = request.current_search.model_dump() if request.current_search else {}

    if llm_complete is None:
        current_state = SearchState(**current)
        return ChatResponse(
            action=ChatAction.ANSWER,
            assistant_message=NOT_CONFIGURED_MESSAGE,
            search=current_state,
            missing_fields=_missing_fields(current),
            recommendation=None,
        )

    try:
        intent = llm_complete(request.message, current)
    except LLMError:
        current_state = SearchState(**current)
        return ChatResponse(
            action=ChatAction.ANSWER,
            assistant_message=LLM_FAILURE_MESSAGE,
            search=current_state,
            missing_fields=_missing_fields(current),
            recommendation=None,
        )

    patch = _sanitize_patch(intent.patch)
    merged = {**current, **patch}

    try:
        merged_state = SearchState(**merged)
    except Exception:
        return _clarify_response(
            "Не удалось применить изменения — проверьте данные и попробуйте снова.",
            SearchState(**current),
        )

    missing = _missing_fields(merged)

    if intent.action == ChatAction.CLARIFY or missing:
        message = intent.message or _default_clarify_message(missing)
        return ChatResponse(
            action=ChatAction.CLARIFY,
            assistant_message=message,
            search=merged_state,
            missing_fields=missing,
            recommendation=None,
        )

    if intent.action == ChatAction.ANSWER:
        return ChatResponse(
            action=ChatAction.ANSWER,
            assistant_message=intent.message or "Хорошо.",
            search=merged_state,
            missing_fields=[],
            recommendation=None,
        )

    # SEARCH / UPDATE_SEARCH, all required fields present.
    assert merged_state.event_date is not None
    if not repo.is_within_calendar_window(merged_state.event_date):
        message = (
            f"Дата {merged_state.event_date.isoformat()} вне доступного периода "
            f"({repo.calendar_start.isoformat()} – {repo.calendar_end.isoformat()}). "
            "Укажите другую дату."
        )
        return ChatResponse(
            action=ChatAction.CLARIFY,
            assistant_message=message,
            search=merged_state,
            missing_fields=[],
            recommendation=None,
        )

    query = RecommendQuery(
        city=merged_state.city,  # type: ignore[arg-type]
        event_date=merged_state.event_date,
        event_format=merged_state.event_format,  # type: ignore[arg-type]
        category=merged_state.category,  # type: ignore[arg-type]
        budget_kzt=merged_state.budget_kzt,  # type: ignore[arg-type]
        duration_hours=merged_state.duration_hours,
        language=merged_state.language,
        preferences=merged_state.preferences,
    )
    result = recommend(query, repo, ranker, evidence_index)
    recommendation = build_recommend_response(query, result)

    assistant_message = intent.message or _default_result_message(merged_state, recommendation)

    return ChatResponse(
        action=intent.action,
        assistant_message=assistant_message,
        search=merged_state,
        missing_fields=[],
        recommendation=recommendation,
    )
