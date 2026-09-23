"""Deterministic, evidence-backed excerpt selection from contractor
descriptions.

Reuses the same E5 encode function as `app.services.semantic` (never loads a
second model, never reloads the model per request). Each contractor
description is deterministically segmented once at construction time and its
segment embeddings are precomputed once; a request only encodes the
`preferences` query text (that encode call already happens once for ranking
in `app.services.semantic.SemanticRanker` — callers pass the resulting query
embedding in here rather than re-encoding).

This module never invents facts: the returned excerpt is always a verbatim
substring of the contractor's own `description` field.
"""

import re

import numpy as np

from app.domain.evidence import EvidenceMatch
from app.domain.models import Contractor
from app.services.semantic import EncodeFn, PASSAGE_PREFIX

# Split on sentence-ending punctuation or newlines. Deliberately simple and
# deterministic — this is segmentation, not NLP sentence parsing.
_SEGMENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

# Segments shorter than this are dropped (list bullets like "•", stray
# fragments) unless they're all a description has, in which case the whole
# description is kept as a single segment.
MIN_SEGMENT_CHARS = 12

# Evidence excerpts are kept short per the explanation grounding rules.
MAX_EXCERPT_CHARS = 220


def segment_description(description: str) -> list[str]:
    text = description.strip()
    if not text:
        return []
    pieces = [p.strip() for p in _SEGMENT_SPLIT_RE.split(text) if p.strip()]
    segments = [p for p in pieces if len(p) >= MIN_SEGMENT_CHARS]
    return segments or [text]


def _truncate(excerpt: str) -> str:
    if len(excerpt) <= MAX_EXCERPT_CHARS:
        return excerpt
    return excerpt[:MAX_EXCERPT_CHARS].rstrip() + "…"


class DescriptionEvidenceIndex:
    """Precomputes description-segment embeddings for the whole catalog once
    and, per request, selects the best-matching segment per contractor
    against an already-encoded preference query embedding.
    """

    def __init__(self, contractors: list[Contractor], encode: EncodeFn):
        self._segments: dict[str, list[str]] = {}
        self._embeddings: dict[str, np.ndarray] = {}

        flat_segments: list[str] = []
        segment_counts: dict[str, int] = {}
        for contractor in contractors:
            segments = segment_description(contractor.description)
            self._segments[contractor.id] = segments
            segment_counts[contractor.id] = len(segments)
            flat_segments.extend(segments)

        flat_embeddings = (
            encode([PASSAGE_PREFIX + s for s in flat_segments])
            if flat_segments
            else np.empty((0, 0))
        )

        offset = 0
        for contractor in contractors:
            n = segment_counts[contractor.id]
            self._embeddings[contractor.id] = flat_embeddings[offset : offset + n]
            offset += n

    def best_segment(
        self, query_embedding: np.ndarray, contractor: Contractor
    ) -> EvidenceMatch | None:
        segments = self._segments.get(contractor.id) or []
        embeddings = self._embeddings.get(contractor.id)
        if not segments or embeddings is None or embeddings.shape[0] == 0:
            return None
        similarities = embeddings @ query_embedding
        best_index = int(np.argmax(similarities))
        return EvidenceMatch(
            excerpt=_truncate(segments[best_index]),
            score=float(similarities[best_index]),
        )
