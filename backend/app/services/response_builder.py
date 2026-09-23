"""Builds the API-facing `RecommendResponse` from a `RecommendResult`.

Shared by `POST /api/v1/recommend` and `POST /api/v1/chat` so both entry
points present the engine's output identically — the chat layer must never
format or re-derive results on its own.
"""

from collections import Counter

from app.schemas.recommend import (
    ContractorCard,
    RecommendationEvidence,
    RecommendResponse,
    RejectedCandidate,
)
from app.services.explanation import build_explanation
from app.services.recommendation import RecommendQuery, RecommendResult
from app.services.semantic import ScoredContractor


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


def build_recommend_response(
    query: RecommendQuery, result: RecommendResult
) -> RecommendResponse:
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
