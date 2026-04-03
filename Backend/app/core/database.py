from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings

_client: MongoClient | None = None
_db: Database | None = None


# Initialize and cache a single MongoDB client for the app process.
def get_database() -> Database:
    global _client, _db

    if _db is None:
        _client = MongoClient(settings.MONGODB_URI, appname="fraud-detection-api")
        _db = _client[settings.MONGODB_DB_NAME]

    return _db


# Ensure required collections exist on startup.
def initialize_collections() -> None:
    db = get_database()
    existing = set(db.list_collection_names())

    for collection_name in ("users", "transactions", "alerts"):
        if collection_name not in existing:
            db.create_collection(collection_name)
