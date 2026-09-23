from functools import lru_cache

from app.config import DATASET_CSV_PATH
from app.repositories.catalog import CatalogRepository
from app.services.evidence import DescriptionEvidenceIndex
from app.services.semantic import EncodeFn, SemanticRanker, default_encoder


@lru_cache
def get_catalog_repository() -> CatalogRepository:
    return CatalogRepository.from_csv(DATASET_CSV_PATH)


@lru_cache
def get_encoder() -> EncodeFn:
    """Loads the embedding model exactly once (per process); shared by the
    semantic ranker and the evidence index so the model is never loaded
    twice.
    """
    return default_encoder()


@lru_cache
def get_semantic_ranker() -> SemanticRanker:
    """Precomputes profile embeddings for the whole catalog exactly once (per
    process), on first use.
    """
    repo = get_catalog_repository()
    return SemanticRanker(repo.all(), get_encoder())


@lru_cache
def get_evidence_index() -> DescriptionEvidenceIndex:
    """Precomputes description-segment embeddings for the whole catalog
    exactly once (per process), on first use.
    """
    repo = get_catalog_repository()
    return DescriptionEvidenceIndex(repo.all(), get_encoder())
