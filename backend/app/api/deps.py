from functools import lru_cache

from app.config import DATASET_CSV_PATH, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.repositories.catalog import CatalogRepository
from app.services.evidence import DescriptionEvidenceIndex
from app.services.llm_client import LLMCompleteFn, openai_complete_factory
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


def catalog_options(repo: CatalogRepository) -> dict[str, list[str]]:
    cities: set[str] = set()
    categories: set[str] = set()
    event_formats: set[str] = set()
    languages: set[str] = set()
    for contractor in repo.all():
        cities.add(contractor.city)
        categories.update(contractor.categories)
        event_formats.update(contractor.event_formats)
        languages.update(contractor.languages)
    return {
        "city": sorted(cities),
        "category": sorted(categories),
        "event_format": sorted(event_formats),
        "language": sorted(languages),
    }


@lru_cache
def get_llm_complete_fn() -> LLMCompleteFn | None:
    """Returns `None` when no chat LLM is configured (`LLM_API_KEY` unset) —
    `/api/v1/chat` stays usable and says so; `/api/v1/recommend` never
    depends on this at all.
    """
    if not LLM_API_KEY:
        return None
    repo = get_catalog_repository()
    return openai_complete_factory(
        LLM_API_KEY, LLM_MODEL, LLM_BASE_URL, catalog_options(repo)
    )
