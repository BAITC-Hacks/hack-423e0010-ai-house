from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Contractor:
    id: str
    name: str
    categories: frozenset[str]
    city: str
    city_imputed: bool
    synthetic: bool
    price_from_kzt: int
    price_imputed: bool
    event_formats: frozenset[str]
    languages: frozenset[str]
    max_hours: int | None
    busy_dates: frozenset[date]
    description: str

    def is_busy_on(self, day: date) -> bool:
        return day in self.busy_dates

    def supports_category(self, category: str) -> bool:
        return category in self.categories

    def supports_format(self, event_format: str) -> bool:
        return event_format in self.event_formats

    def supports_language(self, language: str) -> bool:
        return language in self.languages


@dataclass(frozen=True)
class RejectedCandidate:
    contractor: Contractor
    reasons: tuple[str, ...] = field(default_factory=tuple)
