from datetime import date

import pytest

from app.config import DATASET_CSV_PATH
from app.domain.models import Contractor
from app.repositories.catalog import CatalogRepository


def make_contractor(
    id: str,
    price_from_kzt: int = 100_000,
    city: str = "Алматы",
    categories: frozenset[str] = frozenset({"Ведущий"}),
    event_formats: frozenset[str] = frozenset({"корпоратив"}),
    languages: frozenset[str] = frozenset({"русский"}),
    max_hours: int | None = 8,
    busy_dates: frozenset[date] = frozenset(),
    synthetic: bool = False,
    city_imputed: bool = False,
    price_imputed: bool = False,
    name: str | None = None,
    description: str = "",
) -> Contractor:
    return Contractor(
        id=id,
        name=name or id,
        categories=categories,
        city=city,
        city_imputed=city_imputed,
        synthetic=synthetic,
        price_from_kzt=price_from_kzt,
        price_imputed=price_imputed,
        event_formats=event_formats,
        languages=languages,
        max_hours=max_hours,
        busy_dates=busy_dates,
        description=description,
    )


@pytest.fixture
def real_catalog_repository() -> CatalogRepository:
    return CatalogRepository.from_csv(DATASET_CSV_PATH)
