"""Deterministic, fact-grounded explanation generation for a returned
contractor card.

Every statement in the generated text is traceable to either a structured
field of the request/contractor or a verbatim excerpt selected by
`app.services.evidence`. No LLM is used and no fact is invented — this
module only assembles already-verified data into fixed Russian sentence
templates. Given identical inputs it always produces identical text.
"""

from dataclasses import dataclass
from datetime import date

from app.services.recommendation import RecommendQuery
from app.services.semantic import ScoredContractor

_MONTHS_RU_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def _format_date_ru(day: date) -> str:
    return f"{day.day} {_MONTHS_RU_GENITIVE[day.month]}"


def _format_kzt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₸"


@dataclass(frozen=True)
class Explanation:
    text: str
    available_on_date: bool
    matched_event_format: str
    matched_language: str | None
    requested_duration_hours: int | None
    max_hours: int | None
    price_from_kzt: int
    budget_kzt: int
    semantic_excerpt: str | None
    semantic_score: float | None


def build_explanation(query: RecommendQuery, scored: ScoredContractor) -> Explanation:
    contractor = scored.contractor
    # `query.language` is only set on the request when the caller asked for
    # it — this candidate already passed the hard language filter (§4) so it
    # is a verified match, never an assumption.
    matched_language = query.language if query.language else None

    structured_clauses = [
        f"Свободен {_format_date_ru(query.event_date)}, формат «{query.event_format}»"
        + (f", язык {matched_language}" if matched_language else "")
    ]

    if query.duration_hours is not None:
        if contractor.max_hours is not None:
            structured_clauses.append(
                f"рассчитан до {contractor.max_hours} ч при запросе {query.duration_hours} ч"
            )
        else:
            structured_clauses.append(
                "длительность мероприятия для этой категории не ограничивается"
            )

    structured_clauses.append(
        f"стартовая цена {_format_kzt(contractor.price_from_kzt)} "
        f"укладывается в бюджет {_format_kzt(query.budget_kzt)}"
    )

    sentences = ["; ".join(structured_clauses) + "."]

    semantic_excerpt = scored.evidence.excerpt if scored.evidence is not None else None
    if semantic_excerpt is not None:
        sentences.append(f"В описании подрядчик делает акцент на: «{semantic_excerpt}».")

    return Explanation(
        text=" ".join(sentences),
        available_on_date=True,
        matched_event_format=query.event_format,
        matched_language=matched_language,
        requested_duration_hours=query.duration_hours,
        max_hours=contractor.max_hours,
        price_from_kzt=contractor.price_from_kzt,
        budget_kzt=query.budget_kzt,
        semantic_excerpt=semantic_excerpt,
        semantic_score=scored.semantic_score,
    )
