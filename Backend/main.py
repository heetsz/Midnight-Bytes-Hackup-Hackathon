from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.mongodb import init_collections
from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.transactions import router as transaction_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_collections()
    yield


app = FastAPI(title="Financial Fraud Detection System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transaction_router, prefix="/api", tags=["transactions"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])


@app.get("/")
async def health() -> dict[str, str]:
    return {"message": "Financial Fraud Detection API is running"}
