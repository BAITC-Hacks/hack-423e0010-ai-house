"""Deterministic semantic ranking over eligible contractors using a
multilingual E5 sentence embedding model.

Profile embeddings are precomputed once per catalog (see `SemanticRanker.__init__`)
and reused for every request; only the free-text `preferences` query is encoded
per request. This module never affects eligibility — it only ranks candidates
that already passed the hard filters in `app.services.recommendation`.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.config import EMBEDDING_MODEL_NAME, EMBEDDING_MODEL_REVISION
from app.domain.evidence import EvidenceMatch
from app.domain.models import Contractor

# E5 retrieval convention: queries and passages are encoded with distinct
# prefixes so the model can tell the two roles apart.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

EncodeFn = Callable[[list[str]], np.ndarray]


def build_semantic_document(contractor: Contractor) -> str:
    """Canonical semantic text for a contractor profile.

    Format: "<description>. Категории: <cat1, cat2>. Форматы мероприятий: <f1, f2>."
    `description` is the original full CSV free text (never the shortened
    HTML preview). Categories/event formats are included only for semantic
    context, sorted for determinism — they never gate eligibility here, the
    hard filters in `app.services.recommendation` already did that.
    """
    parts = [contractor.description.strip()]

    categories = ", ".join(sorted(contractor.categories))
    if categories:
        parts.append(f"Категории: {categories}.")

    event_formats = ", ".join(sorted(contractor.event_formats))
    if event_formats:
        parts.append(f"Форматы мероприятий: {event_formats}.")

    return " ".join(part for part in parts if part)


def default_encoder(
    model_name: str = EMBEDDING_MODEL_NAME,
    revision: str | None = EMBEDDING_MODEL_REVISION,
) -> EncodeFn:
    """Builds an `EncodeFn` backed by a real `sentence_transformers` model.

    Import is local so the (heavy) dependency is only touched when this
    factory is actually called, not on module import.

    `revision` pins a specific Hugging Face Hub revision (commit SHA or tag)
    for reproducibility; `None` (the default, unless `EMBEDDING_MODEL_REVISION`
    is set) resolves the repo's default branch at load time.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, revision=revision)

    def encode(texts: list[str]) -> np.ndarray:
        return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)

    return encode


class SemanticRanker:
    """Precomputes contractor profile embeddings once, then scores eligible
    candidates against a free-text preference query.

    Embeddings are L2-normalized, so cosine similarity reduces to a dot
    product — computed here as an in-memory matrix multiply (66 profiles,
    no vector database needed).
    """

    def __init__(self, contractors: list[Contractor], encode: EncodeFn):
        self._encode = encode
        self._ids = [c.id for c in contractors]
        documents = [PASSAGE_PREFIX + build_semantic_document(c) for c in contractors]
        self._profile_embeddings = (
            encode(documents) if documents else np.empty((0, 0))
        )
        self._index = {contractor_id: i for i, contractor_id in enumerate(self._ids)}

    @classmethod
    def from_catalog(
        cls, contractors: list[Contractor], model_name: str = EMBEDDING_MODEL_NAME
    ) -> "SemanticRanker":
        return cls(contractors, default_encoder(model_name))

    def encode_query(self, preferences: str) -> np.ndarray:
        """Encodes the free-text preference query once. Callers that need
        both a ranking score and semantic evidence should call this once and
        reuse the resulting vector (via `score_with_embedding` and
        `DescriptionEvidenceIndex.best_segment`) rather than re-encoding.
        """
        return self._encode([QUERY_PREFIX + preferences.strip()])[0]

    def score_with_embedding(
        self, query_embedding: np.ndarray, candidates: list[Contractor]
    ) -> dict[str, float]:
        return {
            candidate.id: float(
                np.dot(query_embedding, self._profile_embeddings[self._index[candidate.id]])
            )
            for candidate in candidates
            if candidate.id in self._index
        }

    def score(self, preferences: str, candidates: list[Contractor]) -> dict[str, float]:
        """Cosine similarity between the preference query and each candidate's
        precomputed profile embedding. Only encodes the query text — profile
        embeddings are never recomputed here.
        """
        return self.score_with_embedding(self.encode_query(preferences), candidates)


@dataclass(frozen=True)
class ScoredContractor:
    contractor: Contractor
    semantic_score: float | None
    evidence: EvidenceMatch | None = None
