from datetime import date

from pydantic import BaseModel, Field

from app.domain.enums import ChatAction
from app.schemas.recommend import RecommendResponse


class SearchState(BaseModel):
    """Partial/complete search state. All fields optional — the chat
    orchestrator, not Pydantic, decides which are required before it will
    call the recommendation engine.
    """

    city: str | None = None
    event_date: date | None = None
    event_format: str | None = None
    category: str | None = None
    budget_kzt: int | None = Field(default=None, gt=0)
    duration_hours: int | None = Field(default=None, gt=0)
    language: str | None = None
    preferences: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    current_search: SearchState | None = None


class ChatResponse(BaseModel):
    action: ChatAction
    assistant_message: str
    search: SearchState
    missing_fields: list[str] = []
    recommendation: RecommendResponse | None = None
