from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.config import settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global client, db
    client = AsyncIOMotorClient(
        settings.mongodb_url,
        maxPoolSize=50,
        minPoolSize=5,
        maxIdleTimeMS=300000,
        serverSelectionTimeoutMS=5000,
    )
    db = client[settings.mongodb_db_name]
    await ensure_indexes()


async def close_mongo_connection() -> None:
    global client
    if client is not None:
        client.close()


def get_db() -> AsyncIOMotorDatabase:
    if db is None:
        raise RuntimeError("MongoDB not initialized")
    return db


async def ensure_indexes() -> None:
    mongo = get_db()

    await mongo.users.create_index([("user_key", ASCENDING)], unique=True)
    await mongo.users.create_index([("email", ASCENDING)], unique=True)
    await mongo.users.create_index([("phone_no", ASCENDING)], unique=True)

    await mongo.devices.create_index([("device_hash", ASCENDING)], unique=True)

    await mongo.transactions.create_index([("user_key", ASCENDING), ("timestamp", DESCENDING)])
    await mongo.transactions.create_index([("device_hash", ASCENDING), ("timestamp", DESCENDING)])
    await mongo.transactions.create_index([("timestamp", DESCENDING)])
