from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.fraud import router as fraud_router
from app.core.config import settings
from app.core.database import initialize_collections


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_collections()
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fraud_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "AI Fraud Detection API is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.APP_ENV}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
