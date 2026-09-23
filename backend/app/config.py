import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / "backend" / ".env")
DATASET_CSV_PATH = REPO_ROOT / "docs" / "hackathon dataset anonymized .csv"


def _env(name: str, default: str | None = None) -> str | None:
    # An `.env` line like "KEY=" sets KEY to "" rather than leaving it unset;
    # treat blank the same as absent so optional settings keep their real
    # default instead of silently becoming an empty string.
    value = os.environ.get(name)
    return value if value else default

MAX_RESULTS = 3
FIELD_DELIMITER = "|"

# Semantic ranking / evidence model. `EMBEDDING_MODEL_REVISION` pins a
# specific Hugging Face Hub revision (commit SHA or tag) for reproducibility;
# left unset, sentence-transformers resolves the model repo's default branch
# at load time, so an unpinned deployment can silently pick up a different
# revision if the upstream repo changes. See docs/spec.md §6.1 for details.
EMBEDDING_MODEL_NAME = _env("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base")
EMBEDDING_MODEL_REVISION = _env("EMBEDDING_MODEL_REVISION")

# Chat assistant (`POST /api/v1/chat`). Optional — without `LLM_API_KEY` the
# endpoint still responds (telling the client the assistant isn't configured)
# and `/api/v1/recommend` is entirely unaffected. See docs/spec.md and
# README.md for the chat architecture.
LLM_API_KEY = _env("LLM_API_KEY")
LLM_MODEL = _env("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = _env("LLM_BASE_URL")

REQUIRED_SEARCH_FIELDS = (
    "city",
    "event_date",
    "event_format",
    "category",
    "budget_kzt",
)
