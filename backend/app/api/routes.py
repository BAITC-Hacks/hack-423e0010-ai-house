from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    catalog_options,
    get_catalog_repository,
    get_evidence_index,
    get_llm_complete_fn,
    get_semantic_ranker,
)
from app.repositories.catalog import CatalogRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.recommend import CatalogOptions, RecommendRequest, RecommendResponse
from app.services.chat import run_chat
from app.services.evidence import DescriptionEvidenceIndex
from app.services.llm_client import LLMCompleteFn
from app.services.recommendation import RecommendQuery, recommend
from app.services.response_builder import build_recommend_response
from app.services.semantic import SemanticRanker

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/catalog-options", response_model=CatalogOptions)
def catalog_options_route(
    repo: CatalogRepository = Depends(get_catalog_repository),
) -> CatalogOptions:
    options = catalog_options(repo)
    return CatalogOptions(
        cities=options["city"],
        categories=options["category"],
        event_formats=options["event_format"],
        languages=options["language"],
        calendar_start=repo.calendar_start,
        calendar_end=repo.calendar_end,
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
    return build_recommend_response(query, result)


@router.post("/api/v1/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    repo: CatalogRepository = Depends(get_catalog_repository),
    ranker: SemanticRanker = Depends(get_semantic_ranker),
    evidence_index: DescriptionEvidenceIndex = Depends(get_evidence_index),
    llm_complete: LLMCompleteFn | None = Depends(get_llm_complete_fn),
) -> ChatResponse:
    return run_chat(request, repo, ranker, evidence_index, llm_complete)
