from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceMatch:
    """A single description segment selected as semantic evidence.

    `excerpt` is verbatim text taken from the contractor's own `description`
    field (never invented). `score` is the cosine similarity between the
    preference query and this segment's embedding — reused for evidence
    selection only, never surfaced to the user as a probability.
    """

    excerpt: str
    score: float
