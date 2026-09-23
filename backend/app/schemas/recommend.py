from datetime import date

from pydantic import BaseModel, Field

from app.domain.enums import RecommendationStatus


class RecommendRequest(BaseModel):
    city: str = Field(min_length=1)
    event_date: date
    event_format: str = Field(min_length=1)
    category: str = Field(min_length=1)
    budget_kzt: int = Field(gt=0)
    duration_hours: int | None = Field(default=None, gt=0)
    language: str | None = Field(default=None, min_length=1)
    preferences: str | None = None


class ContractorCard(BaseModel):
    id: str
    name: str
    categories: list[str]
    city: str
    price_from_kzt: int
    event_formats: list[str]
    languages: list[str]
    max_hours: int | None
    synthetic: bool
    city_imputed: bool
    price_imputed: bool
    semantic_score: float | None = None


class RejectedCandidate(BaseModel):
    contractor_id: str
    reasons: list[str]


class RecommendResponse(BaseModel):
    status: RecommendationStatus
    results: list[ContractorCard]
    rejected: list[RejectedCandidate]
