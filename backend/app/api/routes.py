from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_catalog_repository, get_evidence_index, get_semantic_ranker
from app.repositories.catalog import CatalogRepository
from app.schemas.recommend import (
    ContractorCard,
    RecommendationEvidence,
    RecommendRequest,
    RecommendResponse,
    RejectedCandidate,
)
from app.services.evidence import DescriptionEvidenceIndex
from app.services.explanation import build_explanation
from app.services.recommendation import RecommendQuery, recommend
from app.services.semantic import ScoredContractor, SemanticRanker

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _to_card(query: RecommendQuery, scored: ScoredContractor) -> ContractorCard:
    contractor = scored.contractor
    explanation = build_explanation(query, scored)
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
        semantic_score=scored.semantic_score,
        explanation=explanation.text,
        evidence=RecommendationEvidence(
            available_on_date=explanation.available_on_date,
            matched_event_format=explanation.matched_event_format,
            matched_language=explanation.matched_language,
            requested_duration_hours=explanation.requested_duration_hours,
            max_hours=explanation.max_hours,
            price_from_kzt=explanation.price_from_kzt,
            budget_kzt=explanation.budget_kzt,
            semantic_excerpt=explanation.semantic_excerpt,
            semantic_score=explanation.semantic_score,
        ),
    )


@router.post("/api/v1/recommend", response_model=RecommendResponse)
def recommend_contractors(
    request: RecommendRequest,
    repo: CatalogRepository = Depends(get_catalog_repository),
    ranker: SemanticRanker = Depends(get_semantic_ranker),
    evidence_index: DescriptionEvidenceIndex = Depends(get_evidence_index),
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
        preferences=request.preferences,
    )
    result = recommend(query, repo, ranker, evidence_index)

    reason_counts: Counter[str] = Counter()
    for rejected in result.rejected:
        reason_counts.update(rejected.reasons)

    return RecommendResponse(
        status=result.status,
        results=[_to_card(query, c) for c in result.results],
        rejected=[
            RejectedCandidate(contractor_id=r.contractor.id, reasons=list(r.reasons))
            for r in result.rejected
        ],
        rejection_summary=dict(reason_counts),
    )
