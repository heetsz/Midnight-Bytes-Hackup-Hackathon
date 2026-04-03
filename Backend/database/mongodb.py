import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fraud_detection_db")

motor_client = AsyncIOMotorClient(MONGO_URI, appname="fraud-detection-api")
sync_client = MongoClient(MONGO_URI, appname="fraud-detection-sync")

_db_async: AsyncIOMotorDatabase = motor_client[DB_NAME]
_db_sync: Database = sync_client[DB_NAME]


def get_db() -> AsyncIOMotorDatabase:
    return _db_async


def get_sync_db() -> Database:
    return _db_sync


async def init_collections() -> None:
    db = get_db()
    required = {
        "users",
        "devices",
        "sessions",
        "transactions",
        "login_attempts",
        "fraud_alerts",
        "user_weekly_stats",
        "fraud_ring_links",
        "model_retrain_queue",
    }

    existing = set(await db.list_collection_names())
    missing = required - existing

    for collection_name in missing:
        await db.create_collection(collection_name)
