from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import get_semantic_ranker
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model and precompute catalog profile embeddings once
    # at startup rather than on the first /recommend request.
    get_semantic_ranker()
    yield


app = FastAPI(title="Event Contractor Recommendation API", lifespan=lifespan)
app.include_router(router)
