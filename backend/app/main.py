from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_evidence_index, get_semantic_ranker
from app.api.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model and precompute catalog profile/segment
    # embeddings once at startup rather than on the first /recommend request.
    get_semantic_ranker()
    get_evidence_index()
    yield


app = FastAPI(title="Event Contractor Recommendation API", lifespan=lifespan)
app.include_router(router)

# Minimal dependency-free demo UI, served at "/". Mounted last so it never
# shadows the API routes above (health/recommend/chat/docs/openapi.json all
# match before this catch-all).
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
