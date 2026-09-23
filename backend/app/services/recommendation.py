from dataclasses import dataclass
from datetime import date

from app.config import MAX_RESULTS
from app.domain.enums import RecommendationStatus, RejectionReason
from app.domain.models import Contractor, RejectedCandidate
from app.repositories.catalog import CatalogRepository
from app.services.semantic import ScoredContractor, SemanticRanker

# Cosine similarities are compared at this precision for tie-breaking so that
# floating-point noise never produces a non-deterministic order; two scores
# within 1e-6 of each other are treated as equal and broken by price/id.
SIMILARITY_TIE_BREAK_DIGITS = 6


@dataclass(frozen=True)
class RecommendQuery:
    city: str
    event_date: date
    event_format: str
    category: str
    budget_kzt: int
    duration_hours: int | None = None
    language: str | None = None
    preferences: str | None = None


@dataclass(frozen=True)
class RecommendResult:
    status: RecommendationStatus
    results: list[ScoredContractor]
    rejected: list[RejectedCandidate]


def _rejection_reasons(contractor: Contractor, query: RecommendQuery) -> tuple[str, ...]:
    reasons: list[str] = []

    if contractor.is_busy_on(query.event_date):
        reasons.append(RejectionReason.BUSY)

    if not contractor.supports_format(query.event_format):
        reasons.append(RejectionReason.FORMAT_UNSUPPORTED)

    if contractor.price_from_kzt > query.budget_kzt:
        reasons.append(RejectionReason.OVER_BUDGET)

    if query.language is not None and not contractor.supports_language(query.language):
        reasons.append(RejectionReason.LANGUAGE_UNSUPPORTED)

    if (
        query.duration_hours is not None
        and contractor.max_hours is not None
        and query.duration_hours > contractor.max_hours
    ):
        reasons.append(RejectionReason.DURATION_EXCEEDED)

    return tuple(reasons)


def _has_preferences(query: RecommendQuery) -> bool:
    return query.preferences is not None and query.preferences.strip() != ""


def _rank_by_price(contractors: list[Contractor]) -> list[Contractor]:
    return sorted(contractors, key=lambda c: (c.price_from_kzt, c.id))


def _rank_by_semantics(
    contractors: list[Contractor], scores: dict[str, float]
) -> list[Contractor]:
    return sorted(
        contractors,
        key=lambda c: (
            -round(scores[c.id], SIMILARITY_TIE_BREAK_DIGITS),
            c.price_from_kzt,
            c.id,
        ),
    )


def recommend(
    query: RecommendQuery,
    repo: CatalogRepository,
    ranker: SemanticRanker | None = None,
) -> RecommendResult:
    candidates = repo.find_by_city_and_category(query.city, query.category)

    if not candidates:
        return RecommendResult(
            status=RecommendationStatus.CATEGORY_ABSENT, results=[], rejected=[]
        )

    eligible: list[Contractor] = []
    rejected: list[RejectedCandidate] = []
    for contractor in candidates:
        reasons = _rejection_reasons(contractor, query)
        if reasons:
            rejected.append(RejectedCandidate(contractor=contractor, reasons=reasons))
        else:
            eligible.append(contractor)

    if not eligible:
        return RecommendResult(
            status=RecommendationStatus.NO_MATCH, results=[], rejected=rejected
        )

    if _has_preferences(query) and ranker is not None:
        scores = ranker.score(query.preferences, eligible)
        ordered = _rank_by_semantics(eligible, scores)
        scored = [
            ScoredContractor(contractor=c, semantic_score=scores[c.id])
            for c in ordered[:MAX_RESULTS]
        ]
    else:
        ordered = _rank_by_price(eligible)
        scored = [
            ScoredContractor(contractor=c, semantic_score=None)
            for c in ordered[:MAX_RESULTS]
        ]

    return RecommendResult(
        status=RecommendationStatus.MATCHED, results=scored, rejected=rejected
    )
