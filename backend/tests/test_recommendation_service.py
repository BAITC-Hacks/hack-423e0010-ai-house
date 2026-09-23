from datetime import date

from app.domain.enums import RecommendationStatus, RejectionReason
from app.repositories.catalog import CatalogRepository
from app.services.recommendation import RecommendQuery, recommend
from tests.conftest import make_contractor

EVENT_DATE = date(2026, 10, 10)

BASE_QUERY = RecommendQuery(
    city="Алматы",
    event_date=EVENT_DATE,
    event_format="корпоратив",
    category="Ведущий",
    budget_kzt=1_000_000,
    duration_hours=6,
    language="русский",
)


def query_with(**overrides) -> RecommendQuery:
    fields = BASE_QUERY.__dict__.copy()
    fields.update(overrides)
    return RecommendQuery(**fields)


def test_busy_contractor_never_returned():
    busy = make_contractor("B1", price_from_kzt=100_000, busy_dates=frozenset({EVENT_DATE}))
    free = make_contractor("B2", price_from_kzt=900_000)
    repo = CatalogRepository([busy, free])

    result = recommend(BASE_QUERY, repo)

    ids = [c.contractor.id for c in result.results]
    assert "B1" not in ids
    assert result.status == RecommendationStatus.MATCHED
    rejected = {r.contractor.id: r.reasons for r in result.rejected}
    assert RejectionReason.BUSY in rejected["B1"]


def test_over_budget_contractor_never_returned():
    cheap = make_contractor("C1", price_from_kzt=500_000)
    expensive = make_contractor("C2", price_from_kzt=5_000_000)
    repo = CatalogRepository([cheap, expensive])

    result = recommend(BASE_QUERY, repo)

    ids = [c.contractor.id for c in result.results]
    assert "C2" not in ids
    rejected = {r.contractor.id: r.reasons for r in result.rejected}
    assert RejectionReason.OVER_BUDGET in rejected["C2"]


def test_unsupported_event_format_excludes_contractor():
    wrong_format = make_contractor("D1", event_formats=frozenset({"свадьба"}))
    repo = CatalogRepository([wrong_format])

    result = recommend(BASE_QUERY, repo)

    assert result.status == RecommendationStatus.NO_MATCH
    rejected = {r.contractor.id: r.reasons for r in result.rejected}
    assert RejectionReason.FORMAT_UNSUPPORTED in rejected["D1"]


def test_language_filtering_applies_when_language_specified():
    wrong_lang = make_contractor("E1", languages=frozenset({"казахский"}))
    repo = CatalogRepository([wrong_lang])

    result = recommend(query_with(language="русский"), repo)

    assert result.status == RecommendationStatus.NO_MATCH
    rejected = {r.contractor.id: r.reasons for r in result.rejected}
    assert RejectionReason.LANGUAGE_UNSUPPORTED in rejected["E1"]


def test_language_ignored_when_not_specified():
    kazakh_only = make_contractor("E2", languages=frozenset({"казахский"}))
    repo = CatalogRepository([kazakh_only])

    result = recommend(query_with(language=None), repo)

    assert result.status == RecommendationStatus.MATCHED
    assert [c.contractor.id for c in result.results] == ["E2"]


def test_duration_filtering_excludes_contractor_with_lower_max_hours():
    short = make_contractor("F1", max_hours=4)
    repo = CatalogRepository([short])

    result = recommend(query_with(duration_hours=6), repo)

    assert result.status == RecommendationStatus.NO_MATCH
    rejected = {r.contractor.id: r.reasons for r in result.rejected}
    assert RejectionReason.DURATION_EXCEEDED in rejected["F1"]


def test_duration_within_max_hours_is_eligible():
    long_enough = make_contractor("F2", max_hours=8)
    repo = CatalogRepository([long_enough])

    result = recommend(query_with(duration_hours=6), repo)

    assert result.status == RecommendationStatus.MATCHED
    assert [c.contractor.id for c in result.results] == ["F2"]


def test_null_max_hours_is_not_applicable_and_never_excludes():
    no_duration_concept = make_contractor("G1", max_hours=None)
    repo = CatalogRepository([no_duration_concept])

    result = recommend(query_with(duration_hours=6), repo)

    assert result.status == RecommendationStatus.MATCHED
    assert [c.contractor.id for c in result.results] == ["G1"]
    assert result.rejected == []


def test_null_max_hours_does_not_get_treated_as_zero():
    # If null were treated as zero, any positive duration request would exclude it.
    no_duration_concept = make_contractor("G2", max_hours=None)
    repo = CatalogRepository([no_duration_concept])

    result = recommend(query_with(duration_hours=1), repo)

    assert "G2" in [c.contractor.id for c in result.results]


def test_maximum_result_size_is_three():
    contractors = [
        make_contractor(f"H{i}", price_from_kzt=100_000 + i) for i in range(5)
    ]
    repo = CatalogRepository(contractors)

    result = recommend(BASE_QUERY, repo)

    assert len(result.results) == 3


def test_same_request_produces_same_ids_in_same_order():
    contractors = [
        make_contractor("I1", price_from_kzt=200_000),
        make_contractor("I2", price_from_kzt=150_000),
        make_contractor("I3", price_from_kzt=150_000),
        make_contractor("I4", price_from_kzt=300_000),
    ]
    repo = CatalogRepository(contractors)

    first = [c.contractor.id for c in recommend(BASE_QUERY, repo).results]
    second = [c.contractor.id for c in recommend(BASE_QUERY, repo).results]

    assert first == second
    # price asc (I2/I3=150k, I1=200k, I4=300k), then id asc tie-break for I2/I3;
    # only 3 of the 4 eligible contractors are returned.
    assert first == ["I2", "I3", "I1"]


def test_changing_only_date_can_change_results_due_to_availability():
    other_date = date(2026, 10, 11)
    contractor = make_contractor(
        "J1", price_from_kzt=100_000, busy_dates=frozenset({EVENT_DATE})
    )
    repo = CatalogRepository([contractor])

    busy_on_requested_date = recommend(BASE_QUERY, repo)
    free_on_other_date = recommend(query_with(event_date=other_date), repo)

    assert "J1" not in [c.contractor.id for c in busy_on_requested_date.results]
    assert "J1" in [c.contractor.id for c in free_on_other_date.results]


def test_category_absent_vs_no_match_are_distinguishable():
    wrong_category_only = make_contractor("K1", categories=frozenset({"Фотограф"}))
    repo_absent = CatalogRepository([wrong_category_only])
    result_absent = recommend(BASE_QUERY, repo_absent)

    right_category_but_over_budget = make_contractor(
        "K2", categories=frozenset({"Ведущий"}), price_from_kzt=5_000_000
    )
    repo_no_match = CatalogRepository([right_category_but_over_budget])
    result_no_match = recommend(BASE_QUERY, repo_no_match)

    assert result_absent.status == RecommendationStatus.CATEGORY_ABSENT
    assert result_no_match.status == RecommendationStatus.NO_MATCH
    assert result_absent.status != result_no_match.status
    assert result_absent.rejected == []
    assert len(result_no_match.rejected) == 1
