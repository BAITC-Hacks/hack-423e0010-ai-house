"""Chat orchestration tests (`app.services.chat.run_chat`).

The LLM is always a fake `LLMCompleteFn` here — no network, no real model —
per CLAUDE.md ("Automated tests MUST mock the LLM and MUST NOT require paid
API/network access"). `run_chat` is framework-independent, so it's exercised
directly rather than through `TestClient`; a couple of end-to-end checks at
the bottom go through the real `/api/v1/chat` route with the LLM dependency
overridden.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm_complete_fn
from app.domain.enums import ChatAction
from app.main import app
from app.schemas.chat import ChatRequest, SearchState
from app.services.chat import run_chat
from app.services.llm_client import LLMIntent, LLMParseError, LLMUnavailableError

pytestmark = pytest.mark.usefixtures("real_catalog_repository_session")


@pytest.fixture
def repo(real_catalog_repository_session):
    return real_catalog_repository_session


def fake_llm(intent: LLMIntent):
    def complete(message: str, current_search: dict) -> LLMIntent:
        return intent

    return complete


def failing_llm(exc: Exception):
    def complete(message: str, current_search: dict) -> LLMIntent:
        raise exc

    return complete


FULL_PATCH = {
    "city": "Алматы",
    "event_date": "2026-10-10",
    "event_format": "корпоратив",
    "category": "Ведущий",
    "budget_kzt": 700_000,
}


def test_full_search_extraction_calls_recommendation_engine(repo):
    intent = LLMIntent(
        action=ChatAction.SEARCH,
        patch=FULL_PATCH,
        message="Нашёл варианты.",
    )
    request = ChatRequest(message="Нужен ведущий в Алматы...", current_search=None)
    response = run_chat(request, repo, None, None, fake_llm(intent))

    assert response.action == ChatAction.SEARCH
    assert response.missing_fields == []
    assert response.search.city == "Алматы"
    assert response.search.event_date == date(2026, 10, 10)
    assert response.recommendation is not None
    assert response.recommendation.status in {"MATCHED", "NO_MATCH"}


def test_date_follow_up_modifies_only_date(repo):
    current = SearchState(**FULL_PATCH)
    intent = LLMIntent(
        action=ChatAction.UPDATE_SEARCH,
        patch={"event_date": "2026-10-17"},
        message="Поменял дату на 17 октября.",
    )
    request = ChatRequest(message="А теперь 17 октября", current_search=current)
    response = run_chat(request, repo, None, None, fake_llm(intent))

    assert response.search.event_date == date(2026, 10, 17)
    assert response.search.city == current.city
    assert response.search.event_format == current.event_format
    assert response.search.category == current.category
    assert response.search.budget_kzt == current.budget_kzt


def test_budget_follow_up_modifies_only_budget(repo):
    current = SearchState(**FULL_PATCH)
    intent = LLMIntent(
        action=ChatAction.UPDATE_SEARCH,
        patch={"budget_kzt": 1_200_000},
        message="Обновил бюджет.",
    )
    request = ChatRequest(message="Бюджет теперь 1 200 000", current_search=current)
    response = run_chat(request, repo, None, None, fake_llm(intent))

    assert response.search.budget_kzt == 1_200_000
    assert response.search.event_date == current.event_date
    assert response.search.city == current.city
    assert response.search.category == current.category


def test_preference_follow_up_preserves_hard_filters(repo):
    current = SearchState(**FULL_PATCH, duration_hours=6, language="русский")
    intent = LLMIntent(
        action=ChatAction.UPDATE_SEARCH,
        patch={"preferences": "повеселее, с танцами"},
        message="Обновил пожелания.",
    )
    request = ChatRequest(message="Хочется повеселее, с танцами", current_search=current)
    response = run_chat(request, repo, None, None, fake_llm(intent))

    assert response.search.preferences == "повеселее, с танцами"
    for field in ("city", "event_date", "event_format", "category", "budget_kzt", "duration_hours", "language"):
        assert getattr(response.search, field) == getattr(current, field)


def test_missing_mandatory_parameters_returns_clarify(repo):
    intent = LLMIntent(
        action=ChatAction.SEARCH,
        patch={"category": "Фотограф"},
        message=None,
    )
    request = ChatRequest(message="Нужен фотограф на свадьбу", current_search=None)
    response = run_chat(request, repo, None, None, fake_llm(intent))

    assert response.action == ChatAction.CLARIFY
    assert response.recommendation is None
    assert set(response.missing_fields) == {"city", "event_date", "event_format", "budget_kzt"}
    assert response.assistant_message


def test_llm_explicit_clarify_is_honored_even_with_full_patch(repo):
    intent = LLMIntent(
        action=ChatAction.CLARIFY,
        patch=FULL_PATCH,
        message="Уточните формат мероприятия.",
    )
    request = ChatRequest(message="ведущий нужен", current_search=None)
    response = run_chat(request, repo, None, None, fake_llm(intent))

    assert response.action == ChatAction.CLARIFY
    assert response.recommendation is None


def test_malformed_llm_output_is_handled_safely(repo):
    request = ChatRequest(message="???", current_search=SearchState(**FULL_PATCH))
    response = run_chat(
        request, repo, None, None, failing_llm(LLMParseError("bad json"))
    )

    assert response.action == ChatAction.ANSWER
    assert response.recommendation is None
    assert response.search.city == "Алматы"  # current_search preserved
    assert response.assistant_message


def test_llm_failure_does_not_become_no_match(repo):
    request = ChatRequest(message="привет", current_search=SearchState(**FULL_PATCH))
    response = run_chat(
        request, repo, None, None, failing_llm(LLMUnavailableError("network down"))
    )

    assert response.recommendation is None
    assert response.action != "NO_MATCH"


def test_unconfigured_llm_returns_clear_message_without_breaking(repo):
    request = ChatRequest(message="Нужен ведущий", current_search=None)
    response = run_chat(request, repo, None, None, None)

    assert response.action == ChatAction.ANSWER
    assert "не настроен" in response.assistant_message
    assert response.recommendation is None


def test_recommendation_engine_is_final_source_of_results(
    repo, real_semantic_ranker, real_evidence_index
):
    # Same query through /api/v1/recommend-equivalent RecommendQuery and
    # through chat must produce the same eligible/result IDs — chat never
    # invents or reorders results itself.
    from app.services.recommendation import RecommendQuery, recommend

    query = RecommendQuery(
        city="Алматы",
        event_date=date(2026, 10, 10),
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=700_000,
    )
    direct = recommend(query, repo, real_semantic_ranker, real_evidence_index)

    intent = LLMIntent(action=ChatAction.SEARCH, patch=FULL_PATCH, message=None)
    request = ChatRequest(message="Нужен ведущий...", current_search=None)
    response = run_chat(
        request, repo, real_semantic_ranker, real_evidence_index, fake_llm(intent)
    )

    assert [c.contractor.id for c in direct.results] == [
        c.id for c in response.recommendation.results
    ]


def test_chat_endpoint_without_llm_configured_via_api():
    client = TestClient(app)
    app.dependency_overrides[get_llm_complete_fn] = lambda: None
    try:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Привет", "current_search": None},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["action"] == "ANSWER"
        assert "не настроен" in body["assistant_message"]
    finally:
        app.dependency_overrides.pop(get_llm_complete_fn, None)


def test_chat_endpoint_with_mocked_llm_via_api():
    client = TestClient(app)
    app.dependency_overrides[get_llm_complete_fn] = lambda: fake_llm(
        LLMIntent(action=ChatAction.SEARCH, patch=FULL_PATCH, message="Готово.")
    )
    try:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Нужен ведущий...", "current_search": None},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["search"]["city"] == "Алматы"
        assert body["recommendation"] is not None
    finally:
        app.dependency_overrides.pop(get_llm_complete_fn, None)
