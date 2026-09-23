from dataclasses import dataclass
from datetime import date

from app.config import MAX_RESULTS
from app.domain.enums import RecommendationStatus, RejectionReason
from app.domain.models import Contractor, RejectedCandidate
from app.repositories.catalog import CatalogRepository


@dataclass(frozen=True)
class RecommendQuery:
    city: str
    event_date: date
    event_format: str
    category: str
    budget_kzt: int
    duration_hours: int | None = None
    language: str | None = None


@dataclass(frozen=True)
class RecommendResult:
    status: RecommendationStatus
    results: list[Contractor]
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


def _rank(contractors: list[Contractor]) -> list[Contractor]:
    return sorted(contractors, key=lambda c: (c.price_from_kzt, c.id))


def recommend(query: RecommendQuery, repo: CatalogRepository) -> RecommendResult:
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

    ranked = _rank(eligible)[:MAX_RESULTS]
    return RecommendResult(
        status=RecommendationStatus.MATCHED, results=ranked, rejected=rejected
    )
