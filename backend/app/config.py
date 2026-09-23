import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_CSV_PATH = REPO_ROOT / "docs" / "hackathon dataset anonymized .csv"

MAX_RESULTS = 3
FIELD_DELIMITER = "|"

# Semantic ranking / evidence model. `EMBEDDING_MODEL_REVISION` pins a
# specific Hugging Face Hub revision (commit SHA or tag) for reproducibility;
# left unset, sentence-transformers resolves the model repo's default branch
# at load time, so an unpinned deployment can silently pick up a different
# revision if the upstream repo changes. See docs/spec.md §6.1 for details.
EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base"
)
EMBEDDING_MODEL_REVISION = os.environ.get("EMBEDDING_MODEL_REVISION")
