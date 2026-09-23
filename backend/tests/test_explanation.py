"""Tests for the Phase 3 evidence-extraction and explanation-generation
layer. Covers: `app.services.evidence`, `app.services.explanation`, and the
`explanation`/`evidence` fields on the HTTP response.
"""

from datetime import date

import numpy as np
import pytest

from app.services.evidence import DescriptionEvidenceIndex, segment_description
from app.services.explanation import build_explanation
from app.services.recommendation import RecommendQuery, recommend
from app.services.semantic import ScoredContractor
from tests.conftest import make_contractor

EVENT_DATE = date(2026, 10, 10)

BASE_QUERY = RecommendQuery(
    city="Алматы",
    event_date=EVENT_DATE,
    event_format="корпоратив",
    category="Ведущий",
    budget_kzt=1_000_000,
)


def query_with(**overrides) -> RecommendQuery:
    fields = BASE_QUERY.__dict__.copy()
    fields.update(overrides)
    return RecommendQuery(**fields)


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


def test_segment_description_splits_on_sentence_boundaries():
    text = "Первое предложение здесь. Второе предложение тоже здесь! Третье предложение тоже?"
    segments = segment_description(text)
    assert segments == [
        "Первое предложение здесь.",
        "Второе предложение тоже здесь!",
        "Третье предложение тоже?",
    ]


def test_segment_description_falls_back_to_whole_text_when_no_segment_survives():
    text = "Коротко"
    assert segment_description(text) == ["Коротко"]


def test_segment_description_empty_text_yields_no_segments():
    assert segment_description("") == []
    assert segment_description("   ") == []


# ---------------------------------------------------------------------------
# DescriptionEvidenceIndex with a fake encoder (exact, deterministic scores)
# ---------------------------------------------------------------------------

VOCAB = ("ALPHA", "BETA", "GAMMA")


def marker_encode(texts: list[str]) -> np.ndarray:
    vectors = []
    for text in texts:
        vec = np.array([1.0 if token in text else 0.0 for token in VOCAB])
        norm = np.linalg.norm(vec)
        vectors.append(vec / norm if norm else vec)
    return np.array(vectors)


def test_best_segment_selects_the_matching_segment():
    contractor = make_contractor(
        "EV1", description="Первое про ALPHA дело. Второе про GAMMA дело."
    )
    index = DescriptionEvidenceIndex([contractor], marker_encode)
    query_embedding = marker_encode(["query: ALPHA"])[0]

    match = index.best_segment(query_embedding, contractor)

    assert match is not None
    assert "ALPHA" in match.excerpt
    assert match.excerpt in contractor.description


def test_best_segment_none_for_empty_description():
    contractor = make_contractor("EV2", description="")
    index = DescriptionEvidenceIndex([contractor], marker_encode)
    query_embedding = marker_encode(["query: ALPHA"])[0]

    assert index.best_segment(query_embedding, contractor) is None


def test_excerpt_is_verbatim_substring_of_description():
    contractor = make_contractor(
        "EV3",
        description="Уникальная фраза про BETA стиль тут. Другая фраза про ALPHA здесь.",
    )
    index = DescriptionEvidenceIndex([contractor], marker_encode)
    query_embedding = marker_encode(["query: BETA"])[0]

    match = index.best_segment(query_embedding, contractor)

    assert match is not None
    assert match.excerpt in contractor.description


# ---------------------------------------------------------------------------
# build_explanation — grounding rules
# ---------------------------------------------------------------------------


def test_explanation_without_preferences_has_no_semantic_content():
    contractor = make_contractor("NX1", price_from_kzt=400_000)
    scored = ScoredContractor(contractor=contractor, semantic_score=None, evidence=None)

    explanation = build_explanation(BASE_QUERY, scored)

    assert explanation.semantic_excerpt is None
    assert explanation.semantic_score is None
    assert "акцент" not in explanation.text


def test_explanation_price_is_phrased_as_starting_price():
    contractor = make_contractor("PX1", price_from_kzt=500_000)
    scored = ScoredContractor(contractor=contractor, semantic_score=None, evidence=None)

    explanation = build_explanation(BASE_QUERY, scored)

    assert "стартовая цена" in explanation.text
    assert "500 000" in explanation.text
    assert "гарантир" not in explanation.text.lower()
    assert "финальн" not in explanation.text.lower()


def test_explanation_marketing_claims_attributed_to_profile_not_asserted():
    from app.domain.evidence import EvidenceMatch

    contractor = make_contractor("MX1", description="Мы №1 в стране по версии рейтинга.")
    evidence = EvidenceMatch(excerpt="Мы №1 в стране по версии рейтинга.", score=0.9)
    scored = ScoredContractor(contractor=contractor, semantic_score=0.9, evidence=evidence)

    explanation = build_explanation(query_with(preferences="лучший"), scored)

    assert "В описании подрядчик делает акцент на" in explanation.text
    # Never asserted as an independently verified fact.
    assert "является №1" not in explanation.text


def test_explanation_null_duration_not_treated_as_zero_or_unlimited():
    contractor = make_contractor("DX1", max_hours=None)
    scored = ScoredContractor(contractor=contractor, semantic_score=None, evidence=None)

    explanation = build_explanation(query_with(duration_hours=6), scored)

    assert explanation.max_hours is None
    assert "не ограничивается" in explanation.text
    assert "0 ч" not in explanation.text


def test_explanation_references_only_request_and_contractor_facts():
    contractor = make_contractor(
        "FX1", price_from_kzt=650_000, max_hours=8, languages=frozenset({"русский"})
    )
    scored = ScoredContractor(contractor=contractor, semantic_score=None, evidence=None)

    explanation = build_explanation(
        query_with(language="русский", duration_hours=6), scored
    )

    assert explanation.matched_language == "русский"
    assert explanation.requested_duration_hours == 6
    assert explanation.max_hours == 8
    assert explanation.price_from_kzt == 650_000
    assert explanation.budget_kzt == BASE_QUERY.budget_kzt


# ---------------------------------------------------------------------------
# Determinism and differentiation
# ---------------------------------------------------------------------------


def test_identical_inputs_produce_identical_explanation_text():
    contractor = make_contractor("ID1", price_from_kzt=500_000)
    scored = ScoredContractor(contractor=contractor, semantic_score=0.5, evidence=None)

    first = build_explanation(BASE_QUERY, scored)
    second = build_explanation(BASE_QUERY, scored)

    assert first.text == second.text


def test_different_contractors_produce_different_explanation_text():
    from app.domain.evidence import EvidenceMatch

    cheap = make_contractor("DF1", price_from_kzt=300_000, max_hours=6)
    pricey = make_contractor("DF2", price_from_kzt=900_000, max_hours=10)
    scored_cheap = ScoredContractor(
        contractor=cheap,
        semantic_score=0.7,
        evidence=EvidenceMatch(excerpt="Спокойный деловой стиль ведения.", score=0.7),
    )
    scored_pricey = ScoredContractor(
        contractor=pricey,
        semantic_score=0.6,
        evidence=EvidenceMatch(excerpt="Энергичное шоу с танцами.", score=0.6),
    )

    text_cheap = build_explanation(query_with(duration_hours=6), scored_cheap).text
    text_pricey = build_explanation(query_with(duration_hours=6), scored_pricey).text

    assert text_cheap != text_pricey


# ---------------------------------------------------------------------------
# End-to-end via recommend() with the real model / real dataset
# ---------------------------------------------------------------------------


def test_every_returned_contractor_has_an_explanation(
    real_catalog_repository_session, real_semantic_ranker, real_evidence_index
):
    query = RecommendQuery(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_000_000,
        duration_hours=6,
        language="русский",
        preferences="спокойная деловая интеллигентная подача, корпоративный стиль",
    )
    result = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )

    assert result.results
    for scored in result.results:
        explanation = build_explanation(query, scored)
        assert explanation.text.strip() != ""


def test_semantic_evidence_comes_from_the_contractor_description(
    real_catalog_repository_session, real_semantic_ranker, real_evidence_index
):
    query = RecommendQuery(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_000_000,
        preferences="спокойная деловая интеллигентная подача",
    )
    result = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )

    assert result.results
    for scored in result.results:
        assert scored.evidence is not None
        assert scored.evidence.excerpt in scored.contractor.description


def test_semantic_evidence_null_without_preferences(
    real_catalog_repository_session, real_semantic_ranker, real_evidence_index
):
    query = RecommendQuery(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_000_000,
    )
    result = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )

    assert result.results
    for scored in result.results:
        assert scored.evidence is None
        explanation = build_explanation(query, scored)
        assert explanation.semantic_excerpt is None


def test_busy_and_ineligible_contractors_still_excluded_with_evidence_enabled(
    real_catalog_repository_session, real_semantic_ranker, real_evidence_index
):
    query = RecommendQuery(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_000_000,
        preferences="спокойная деловая интеллигентная подача",
    )
    result = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )
    result_no_evidence = recommend(query, real_catalog_repository_session, real_semantic_ranker)

    # Evidence extraction must never change eligibility or ranking.
    assert [c.contractor.id for c in result.results] == [
        c.contractor.id for c in result_no_evidence.results
    ]
    rejected_ids = {r.contractor.id for r in result.rejected}
    assert rejected_ids == {r.contractor.id for r in result_no_evidence.rejected}
    assert not rejected_ids & {c.contractor.id for c in result.results}


def test_different_contractors_yield_meaningfully_different_explanations_real_data(
    real_catalog_repository_session, real_semantic_ranker, real_evidence_index
):
    query = RecommendQuery(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_000_000,
        duration_hours=6,
        language="русский",
        preferences="спокойная деловая интеллигентная подача, корпоративный стиль",
    )
    result = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )

    assert len(result.results) >= 2
    texts = [build_explanation(query, c).text for c in result.results]
    assert len(set(texts)) == len(texts)


def test_repeated_identical_requests_produce_identical_explanation_text(
    real_catalog_repository_session, real_semantic_ranker, real_evidence_index
):
    query = RecommendQuery(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=1_000_000,
        preferences="спокойная деловая интеллигентная подача",
    )
    first = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )
    second = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )

    first_texts = [build_explanation(query, c).text for c in first.results]
    second_texts = [build_explanation(query, c).text for c in second.results]
    assert first_texts == second_texts


def test_no_llm_or_network_required_to_build_explanation():
    # `build_explanation` is a pure function over already-computed data —
    # no HTTP client, no model, no randomness.
    contractor = make_contractor("PURE1", price_from_kzt=500_000)
    scored = ScoredContractor(contractor=contractor, semantic_score=None, evidence=None)
    explanation = build_explanation(BASE_QUERY, scored)
    assert isinstance(explanation.text, str)
