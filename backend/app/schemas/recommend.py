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


class RecommendationEvidence(BaseModel):
    """Structured facts backing `ContractorCard.explanation`. Every field is
    either a verified structured match/value or a verbatim excerpt from the
    contractor's own description — never an invented claim.
    """

    available_on_date: bool
    matched_event_format: str
    matched_language: str | None
    requested_duration_hours: int | None
    max_hours: int | None
    price_from_kzt: int
    budget_kzt: int
    semantic_excerpt: str | None = None
    semantic_score: float | None = None


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
    explanation: str
    evidence: RecommendationEvidence


class RejectedCandidate(BaseModel):
    contractor_id: str
    reasons: list[str]


class RecommendResponse(BaseModel):
    status: RecommendationStatus
    results: list[ContractorCard]
    rejected: list[RejectedCandidate]
    rejection_summary: dict[str, int] = {}


class CatalogOptions(BaseModel):
    """Known allowed values, for building a form that never invents
    unsupported categories/formats/etc.
    """

    cities: list[str]
    categories: list[str]
    event_formats: list[str]
    languages: list[str]
    calendar_start: date | None
    calendar_end: date | None
