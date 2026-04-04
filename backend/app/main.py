from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_mongo_connection, connect_to_mongo
from app.routers.dashboard import router as dashboard_router
from app.routers.devices import router as devices_router
from app.routers.transactions import router as transactions_router
from app.routers.users import public_router as user_public_router
from app.routers.users import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(
    title="Fraud Ops Mongo Backend",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


app.include_router(users_router)
app.include_router(user_public_router)
app.include_router(devices_router)
app.include_router(transactions_router)
app.include_router(dashboard_router)
