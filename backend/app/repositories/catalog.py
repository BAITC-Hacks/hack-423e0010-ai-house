import csv
from datetime import date, datetime
from pathlib import Path

from app.config import FIELD_DELIMITER
from app.domain.models import Contractor


def _split(raw: str) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(FIELD_DELIMITER) if part.strip())


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() == "true"


def _parse_dates(raw: str) -> frozenset[date]:
    if not raw:
        return frozenset()
    return frozenset(
        datetime.strptime(part.strip(), "%Y-%m-%d").date()
        for part in raw.split(FIELD_DELIMITER)
        if part.strip()
    )


def _row_to_contractor(row: dict[str, str]) -> Contractor:
    max_hours_raw = row["max_hours"].strip()
    return Contractor(
        id=row["id"].strip(),
        name=row["anon_name"].strip(),
        categories=_split(row["categories"]),
        city=row["city"].strip(),
        city_imputed=_parse_bool(row["city_imputed"]),
        synthetic=_parse_bool(row["synthetic"]),
        price_from_kzt=int(row["price_from_kzt"]),
        price_imputed=_parse_bool(row["price_imputed"]),
        event_formats=_split(row["event_formats"]),
        languages=_split(row["languages"]),
        max_hours=int(max_hours_raw) if max_hours_raw else None,
        busy_dates=_parse_dates(row["busy_dates"]),
        description=row["description"].strip(),
    )


def load_contractors(csv_path: Path) -> list[Contractor]:
    with csv_path.open(encoding="utf-8", newline="") as f:
        return [_row_to_contractor(row) for row in csv.DictReader(f)]


class CatalogRepository:
    """In-memory contractor catalog loaded once from the dataset CSV."""

    def __init__(self, contractors: list[Contractor]):
        self._contractors = contractors
        self._calendar_start, self._calendar_end = self._compute_calendar_window(contractors)

    @classmethod
    def from_csv(cls, csv_path: Path) -> "CatalogRepository":
        return cls(load_contractors(csv_path))

    @staticmethod
    def _compute_calendar_window(
        contractors: list[Contractor],
    ) -> tuple[date | None, date | None]:
        all_dates = {d for c in contractors for d in c.busy_dates}
        if not all_dates:
            return None, None
        return min(all_dates), max(all_dates)

    @property
    def calendar_start(self) -> date | None:
        return self._calendar_start

    @property
    def calendar_end(self) -> date | None:
        return self._calendar_end

    def is_within_calendar_window(self, day: date) -> bool:
        if self._calendar_start is None or self._calendar_end is None:
            return False
        return self._calendar_start <= day <= self._calendar_end

    def all(self) -> list[Contractor]:
        return list(self._contractors)

    def find_by_city_and_category(self, city: str, category: str) -> list[Contractor]:
        return [
            c
            for c in self._contractors
            if c.city == city and c.supports_category(category)
        ]
