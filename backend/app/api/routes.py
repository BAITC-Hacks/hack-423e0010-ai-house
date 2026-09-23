from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_catalog_repository
from app.domain.models import Contractor
from app.repositories.catalog import CatalogRepository
from app.schemas.recommend import (
    ContractorCard,
    RecommendRequest,
    RecommendResponse,
    RejectedCandidate,
)
from app.services.recommendation import RecommendQuery, recommend

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _to_card(contractor: Contractor) -> ContractorCard:
    return ContractorCard(
        id=contractor.id,
        name=contractor.name,
        categories=sorted(contractor.categories),
        city=contractor.city,
        price_from_kzt=contractor.price_from_kzt,
        event_formats=sorted(contractor.event_formats),
        languages=sorted(contractor.languages),
        max_hours=contractor.max_hours,
        synthetic=contractor.synthetic,
        city_imputed=contractor.city_imputed,
        price_imputed=contractor.price_imputed,
    )


@router.post("/api/v1/recommend", response_model=RecommendResponse)
def recommend_contractors(
    request: RecommendRequest,
    repo: CatalogRepository = Depends(get_catalog_repository),
) -> RecommendResponse:
    if not repo.is_within_calendar_window(request.event_date):
        raise HTTPException(
            status_code=422,
            detail=(
                f"event_date {request.event_date.isoformat()} is outside the known "
                f"availability calendar window "
                f"({repo.calendar_start.isoformat()} to {repo.calendar_end.isoformat()})."
            ),
        )

    query = RecommendQuery(
        city=request.city,
        event_date=request.event_date,
        event_format=request.event_format,
        category=request.category,
        budget_kzt=request.budget_kzt,
        duration_hours=request.duration_hours,
        language=request.language,
    )
    result = recommend(query, repo)

    return RecommendResponse(
        status=result.status,
        results=[_to_card(c) for c in result.results],
        rejected=[
            RejectedCandidate(contractor_id=r.contractor.id, reasons=list(r.reasons))
            for r in result.rejected
        ],
    )
