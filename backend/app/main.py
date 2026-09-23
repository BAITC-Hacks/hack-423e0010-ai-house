from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="Event Contractor Recommendation API")
app.include_router(router)
