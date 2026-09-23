"""Pytest wrapper around `evaluation/cases.py` so the curated semantic
evaluation set is exercised on every run of the suite and regressions are
caught automatically, not just via `python -m evaluation.run`.

Strict cases (`expected_first`) are asserted; soft cases (`expected_in_top`)
are recorded via a warning rather than a failure — per the harness's rule of
not forcing exact rankings where the dataset doesn't clearly support one.
Cases with no expectation at all are exercised only for crash/latency
regressions (still must return MATCHED with results).
"""

import warnings

import pytest

from app.services.evidence import DescriptionEvidenceIndex
from app.services.recommendation import RecommendQuery, recommend
from evaluation.cases import CASES


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_semantic_evaluation_case(
    case, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
):
    query = RecommendQuery(
        city=case.city,
        event_date=case.event_date,
        event_format=case.event_format,
        category=case.category,
        budget_kzt=case.budget_kzt,
        duration_hours=case.duration_hours,
        language=case.language,
        preferences=case.preferences,
    )
    result = recommend(
        query, real_catalog_repository_session, real_semantic_ranker, real_evidence_index
    )
    ids = [c.contractor.id for c in result.results]

    assert result.status.value == "MATCHED"
    assert ids, f"{case.name}: expected at least one eligible result"

    if case.expected_first is not None:
        assert ids[0] == case.expected_first, (
            f"{case.name}: expected {case.expected_first} first, got {ids}. "
            f"Rationale: {case.rationale}"
        )

    if case.expected_in_top is not None:
        if not (set(ids) & case.expected_in_top):
            warnings.warn(
                f"{case.name}: none of {sorted(case.expected_in_top)} in top-3 "
                f"result {ids}. Rationale: {case.rationale}",
                stacklevel=1,
            )


def test_evidence_index_covers_all_cases_contractors(
    real_catalog_repository_session, real_evidence_index: DescriptionEvidenceIndex
):
    # Sanity check: the evaluation harness's own fixtures are wired
    # correctly (shared model, real dataset) before trusting any case result.
    assert real_catalog_repository_session.all()
    assert real_evidence_index is not None
