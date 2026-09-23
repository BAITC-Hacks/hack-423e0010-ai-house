from datetime import date

import pytest

from app.config import DATASET_CSV_PATH
from app.domain.models import Contractor
from app.repositories.catalog import CatalogRepository
from app.services.semantic import SemanticRanker


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


@pytest.fixture(scope="session")
def real_catalog_repository_session() -> CatalogRepository:
    # Session-scoped so the CSV-backed catalog used by the real embedding
    # model is loaded once per test run, not once per test.
    return CatalogRepository.from_csv(DATASET_CSV_PATH)


@pytest.fixture(scope="session")
def real_semantic_ranker(real_catalog_repository_session: CatalogRepository) -> SemanticRanker:
    # Loads intfloat/multilingual-e5-base and precomputes profile embeddings
    # for the whole catalog exactly once per test session.
    return SemanticRanker.from_catalog(real_catalog_repository_session.all())
