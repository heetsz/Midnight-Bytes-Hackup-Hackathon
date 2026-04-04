from datetime import datetime, timezone
from bson import ObjectId


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_object_id(value: str) -> ObjectId:
    return ObjectId(value)


def serialize_id(document: dict) -> dict:
    if not document:
        return document
    document["_id"] = str(document["_id"])
    return document
