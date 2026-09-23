from functools import lru_cache

from app.config import DATASET_CSV_PATH
from app.repositories.catalog import CatalogRepository


@lru_cache
def get_catalog_repository() -> CatalogRepository:
    return CatalogRepository.from_csv(DATASET_CSV_PATH)
