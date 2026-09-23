from functools import lru_cache

from app.config import DATASET_CSV_PATH
from app.repositories.catalog import CatalogRepository
from app.services.semantic import SemanticRanker


@lru_cache
def get_catalog_repository() -> CatalogRepository:
    return CatalogRepository.from_csv(DATASET_CSV_PATH)


@lru_cache
def get_semantic_ranker() -> SemanticRanker:
    """Loads the embedding model and precomputes profile embeddings for the
    whole catalog exactly once (per process), on first use.
    """
    repo = get_catalog_repository()
    return SemanticRanker.from_catalog(repo.all())
