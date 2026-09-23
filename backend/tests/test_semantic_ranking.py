from datetime import date

import numpy as np
import pytest

from app.domain.enums import RecommendationStatus
from app.repositories.catalog import CatalogRepository
from app.services.recommendation import RecommendQuery, recommend
from app.services.semantic import SemanticRanker
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
# A controllable fake encoder for tests that only exercise ranking *logic*
# (eligibility isolation, ordering, call counts). It never needs real
# semantic meaning: it maps each vocabulary token to its own axis and scores
# a text 1.0 on that axis iff the token substring is present. This gives
# exact, predictable cosine similarities without loading the real model.
# ---------------------------------------------------------------------------
VOCAB = ("ALPHA", "BETA", "GAMMA")


def marker_ranker(contractors, vocab=VOCAB):
    calls = {"count": 0}

    def encode(texts: list[str]) -> np.ndarray:
        calls["count"] += 1
        vectors = []
        for text in texts:
            vec = np.array([1.0 if token in text else 0.0 for token in vocab])
            norm = np.linalg.norm(vec)
            vectors.append(vec / norm if norm else vec)
        return np.array(vectors)

    return SemanticRanker(contractors, encode), calls


def test_preferences_trigger_semantic_ranking():
    strong_match = make_contractor("S1", price_from_kzt=500_000, description="ALPHA event")
    weak_match = make_contractor("S2", price_from_kzt=100_000, description="GAMMA event")
    contractors = [strong_match, weak_match]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="ALPHA"), repo, ranker)

    assert result.status == RecommendationStatus.MATCHED
    # Cheaper GAMMA contractor would win on price alone; ALPHA preference flips it.
    assert [c.contractor.id for c in result.results] == ["S1", "S2"]
    assert all(c.semantic_score is not None for c in result.results)


def test_empty_preferences_preserve_phase1_price_ranking():
    cheaper = make_contractor("P1", price_from_kzt=100_000, description="GAMMA")
    pricier = make_contractor("P2", price_from_kzt=200_000, description="ALPHA")
    contractors = [cheaper, pricier]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences=""), repo, ranker)

    assert [c.contractor.id for c in result.results] == ["P1", "P2"]
    assert all(c.semantic_score is None for c in result.results)


def test_none_preferences_preserve_phase1_price_ranking():
    cheaper = make_contractor("PN1", price_from_kzt=100_000, description="GAMMA")
    pricier = make_contractor("PN2", price_from_kzt=200_000, description="ALPHA")
    contractors = [cheaper, pricier]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences=None), repo, ranker)

    assert [c.contractor.id for c in result.results] == ["PN1", "PN2"]
    assert all(c.semantic_score is None for c in result.results)


def test_whitespace_only_preferences_preserve_phase1_ranking():
    cheaper = make_contractor("W1", price_from_kzt=100_000, description="GAMMA")
    pricier = make_contractor("W2", price_from_kzt=200_000, description="ALPHA")
    contractors = [cheaper, pricier]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="   \n\t  "), repo, ranker)

    assert [c.contractor.id for c in result.results] == ["W1", "W2"]
    assert all(c.semantic_score is None for c in result.results)


def test_semantic_ranking_only_among_eligible_candidates():
    eligible = make_contractor("EL1", price_from_kzt=100_000, description="GAMMA")
    ineligible_wrong_format = make_contractor(
        "IN1",
        price_from_kzt=100_000,
        description="ALPHA",
        event_formats=frozenset({"свадьба"}),
    )
    contractors = [eligible, ineligible_wrong_format]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="ALPHA"), repo, ranker)

    assert [c.contractor.id for c in result.results] == ["EL1"]
    assert "IN1" in {r.contractor.id for r in result.rejected}


def test_busy_contractor_with_strong_semantic_match_never_returned():
    busy_strong_match = make_contractor(
        "BZ1",
        price_from_kzt=100_000,
        description="ALPHA",
        busy_dates=frozenset({EVENT_DATE}),
    )
    free_weak_match = make_contractor("FR1", price_from_kzt=900_000, description="GAMMA")
    contractors = [busy_strong_match, free_weak_match]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="ALPHA"), repo, ranker)

    ids = [c.contractor.id for c in result.results]
    assert "BZ1" not in ids
    assert "FR1" in ids
    assert "BZ1" in {r.contractor.id for r in result.rejected}


def test_over_budget_contractor_with_strong_semantic_match_never_returned():
    over_budget_strong_match = make_contractor(
        "OB1", price_from_kzt=5_000_000, description="ALPHA"
    )
    affordable_weak_match = make_contractor("AF1", price_from_kzt=900_000, description="GAMMA")
    contractors = [over_budget_strong_match, affordable_weak_match]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="ALPHA"), repo, ranker)

    ids = [c.contractor.id for c in result.results]
    assert "OB1" not in ids
    assert "AF1" in ids
    assert "OB1" in {r.contractor.id for r in result.rejected}


def test_structured_fields_override_contradictory_description_with_semantic_ranking():
    # Description text claims relevance ("ALPHA") but the structured event
    # format field says this contractor only does weddings — must still be
    # rejected even though it would win on semantic score.
    misleading_description = make_contractor(
        "LIE1",
        price_from_kzt=100_000,
        description="ALPHA корпоратив conference",
        event_formats=frozenset({"свадьба"}),
    )
    honest = make_contractor("HON1", price_from_kzt=900_000, description="GAMMA")
    contractors = [misleading_description, honest]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="ALPHA"), repo, ranker)

    ids = [c.contractor.id for c in result.results]
    assert "LIE1" not in ids
    assert "LIE1" in {r.contractor.id for r in result.rejected}


def test_result_count_max_three_with_semantic_ranking():
    contractors = [
        make_contractor(f"M{i}", price_from_kzt=100_000 + i, description="ALPHA")
        for i in range(5)
    ]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="ALPHA"), repo, ranker)

    assert len(result.results) == 3


def test_semantic_scores_correspond_to_returned_contractors_and_are_sorted():
    a = make_contractor("SC1", price_from_kzt=100_000, description="ALPHA")
    b = make_contractor("SC2", price_from_kzt=100_000, description="BETA")
    c = make_contractor("SC3", price_from_kzt=100_000, description="GAMMA")
    contractors = [a, b, c]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    result = recommend(query_with(preferences="ALPHA"), repo, ranker)

    scores = {r.contractor.id: r.semantic_score for r in result.results}
    assert scores["SC1"] == pytest.approx(1.0)
    ordered_scores = [r.semantic_score for r in result.results]
    assert ordered_scores == sorted(ordered_scores, reverse=True)


def test_repeated_identical_fake_ranker_queries_produce_identical_order():
    contractors = [
        make_contractor("R1", price_from_kzt=100_000, description="ALPHA"),
        make_contractor("R2", price_from_kzt=200_000, description="BETA"),
    ]
    ranker, _ = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    first = recommend(query_with(preferences="ALPHA BETA"), repo, ranker)
    second = recommend(query_with(preferences="ALPHA BETA"), repo, ranker)

    assert [c.contractor.id for c in first.results] == [c.contractor.id for c in second.results]
    assert [c.semantic_score for c in first.results] == [c.semantic_score for c in second.results]


def test_profile_embeddings_not_recomputed_per_request():
    contractors = [
        make_contractor(f"N{i}", price_from_kzt=100_000 + i, description="ALPHA")
        for i in range(3)
    ]
    ranker, calls = marker_ranker(contractors)
    repo = CatalogRepository(contractors)

    # One batch-encode call happened at ranker construction time, for all
    # profiles at once.
    assert calls["count"] == 1

    recommend(query_with(preferences="ALPHA"), repo, ranker)
    recommend(query_with(preferences="BETA"), repo, ranker)
    recommend(query_with(preferences="GAMMA"), repo, ranker)

    # Exactly one additional encode call per request (the query text only) —
    # the profile embeddings are never recomputed.
    assert calls["count"] == 1 + 3


# ---------------------------------------------------------------------------
# Real-model tests against the real dataset (session-scoped fixtures so the
# model loads and the catalog embeddings are precomputed only once).
# ---------------------------------------------------------------------------


def test_real_model_repeated_identical_preferences_produce_identical_order(
    real_catalog_repository_session, real_semantic_ranker
):
    query = RecommendQuery(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=700_000,
        preferences="спокойная деловая интеллигентная подача, корпоративный стиль",
    )

    first = recommend(query, real_catalog_repository_session, real_semantic_ranker)
    second = recommend(query, real_catalog_repository_session, real_semantic_ranker)

    assert [c.contractor.id for c in first.results] == [c.contractor.id for c in second.results]
    assert [c.semantic_score for c in first.results] == [c.semantic_score for c in second.results]


def test_real_model_different_preferences_change_ranking_of_same_eligible_pool(
    real_catalog_repository_session, real_semantic_ranker
):
    base = dict(
        city="Алматы",
        event_date=EVENT_DATE,
        event_format="корпоратив",
        category="Ведущий",
        budget_kzt=700_000,
    )

    no_preferences = recommend(
        RecommendQuery(**base), real_catalog_repository_session, real_semantic_ranker
    )
    business_style = recommend(
        RecommendQuery(
            **base, preferences="спокойная деловая интеллигентная подача, корпоративный стиль"
        ),
        real_catalog_repository_session,
        real_semantic_ranker,
    )
    dance_entertainment = recommend(
        RecommendQuery(**base, preferences="яркое шоу с танцами и развлечениями"),
        real_catalog_repository_session,
        real_semantic_ranker,
    )

    eligible_ids = {c.contractor.id for c in no_preferences.results}
    assert eligible_ids == {c.contractor.id for c in business_style.results}
    assert eligible_ids == {c.contractor.id for c in dance_entertainment.results}

    # Same eligible pool, different order: the "dance/entertainment" host
    # (HK-29829) should rank above the "modern professional host" (HK-88430)
    # only when preferences favor entertainment.
    assert [c.contractor.id for c in business_style.results][0] == "HK-88430"
    assert [c.contractor.id for c in dance_entertainment.results][0] == "HK-29829"
