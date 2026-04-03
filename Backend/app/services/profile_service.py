from datetime import datetime
from typing import Any

from pymongo.database import Database

from app.models.schemas import TransactionRequest


def get_or_create_user_profile(db: Database, user_id: str) -> dict[str, Any]:
    users = db["users"]
    profile = users.find_one({"user_id": user_id})

    if profile:
        return profile

    new_profile = {
        "user_id": user_id,
        "total_transactions": 0,
        "avg_amount": 0.0,
        "locations": [],
        "devices": [],
        "hour_activity": {},
        "last_seen": None,
    }
    users.insert_one(new_profile)
    return new_profile


# Update profile metrics using current transaction behavior.
def update_user_profile(db: Database, payload: TransactionRequest) -> dict[str, Any]:
    users = db["users"]
    profile = get_or_create_user_profile(db, payload.user_id)

    previous_count = int(profile.get("total_transactions", 0))
    previous_avg = float(profile.get("avg_amount", 0.0))

    new_count = previous_count + 1
    new_avg = ((previous_avg * previous_count) + payload.amount) / new_count

    locations = list(profile.get("locations", []))
    if payload.location not in locations:
        locations.append(payload.location)

    devices = list(profile.get("devices", []))
    if payload.device not in devices:
        devices.append(payload.device)

    hour_key = str(payload.timestamp.hour)
    hour_activity = dict(profile.get("hour_activity", {}))
    hour_activity[hour_key] = int(hour_activity.get(hour_key, 0)) + 1

    users.update_one(
        {"user_id": payload.user_id},
        {
            "$set": {
                "total_transactions": new_count,
                "avg_amount": round(new_avg, 2),
                "locations": locations,
                "devices": devices,
                "hour_activity": hour_activity,
                "last_seen": datetime.utcnow(),
            }
        },
        upsert=True,
    )

    return {
        **profile,
        "total_transactions": new_count,
        "avg_amount": round(new_avg, 2),
        "locations": locations,
        "devices": devices,
        "hour_activity": hour_activity,
    }
