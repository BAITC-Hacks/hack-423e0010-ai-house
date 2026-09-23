"""Standalone runner for the semantic-ranking evaluation cases.

Usage:
    cd backend && source .venv/bin/activate && python -m evaluation.run

Runs each case in `evaluation/cases.py` through the real recommendation
engine (real dataset, real E5 model) and reports whether the case's
expectation (if any) held, plus the actual top-3 ids/scores/evidence for
manual inspection. Exits non-zero if a strict (`expected_first`) case fails,
so it can be wired into CI as a semantic-regression smoke test; soft
(`expected_in_top`) failures are reported but do not fail the run, per the
"do not force exact rankings" rule.
"""

import sys

from app.config import DATASET_CSV_PATH
from app.repositories.catalog import CatalogRepository
from app.services.evidence import DescriptionEvidenceIndex
from app.services.recommendation import RecommendQuery, recommend
from app.services.semantic import SemanticRanker, default_encoder
from evaluation.cases import CASES


def main() -> int:
    repo = CatalogRepository.from_csv(DATASET_CSV_PATH)
    encoder = default_encoder()
    ranker = SemanticRanker(repo.all(), encoder)
    evidence_index = DescriptionEvidenceIndex(repo.all(), encoder)

    strict_failures = []
    soft_failures = []

    for case in CASES:
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
        result = recommend(query, repo, ranker, evidence_index)
        ids = [c.contractor.id for c in result.results]

        print(f"\n=== {case.name} ({case.intent}) ===")
        print(f"status={result.status}, eligible_top3={ids}")
        for scored in result.results:
            excerpt = scored.evidence.excerpt if scored.evidence else None
            print(
                f"  {scored.contractor.id} score={scored.semantic_score:.4f} "
                f"evidence={excerpt!r}"
            )

        if case.expected_first is not None:
            ok = bool(ids) and ids[0] == case.expected_first
            print(f"  [strict] expected_first={case.expected_first} -> {'OK' if ok else 'FAIL'}")
            if not ok:
                strict_failures.append(case.name)

        if case.expected_in_top is not None:
            ok = bool(set(ids) & case.expected_in_top)
            print(
                f"  [soft] expected_in_top={sorted(case.expected_in_top)} -> "
                f"{'OK' if ok else 'FAIL'}"
            )
            if not ok:
                soft_failures.append(case.name)

    print(f"\n{len(CASES)} cases run, {len(strict_failures)} strict failures, "
          f"{len(soft_failures)} soft failures.")
    if strict_failures:
        print(f"STRICT FAILURES: {strict_failures}")
    if soft_failures:
        print(f"SOFT FAILURES (reported, non-blocking): {soft_failures}")

    return 1 if strict_failures else 0


if __name__ == "__main__":
    sys.exit(main())
