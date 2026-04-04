import hashlib
import json

from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.schemas import DeviceRegisterRequest
from app.utils.mongo import serialize_id, utc_now

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_device(payload: DeviceRegisterRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    raw = json.dumps(payload.fingerprint.model_dump(), sort_keys=True, separators=(",", ":"))
    device_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    existing = await db.devices.find_one({"device_hash": device_hash})
    if existing:
        return {"created": False, "device": serialize_id(existing)}

    doc = {
        "device_hash": device_hash,
        "created_at": utc_now(),
        "fingerprint": payload.fingerprint.model_dump(),
    }
    result = await db.devices.insert_one(doc)
    created = await db.devices.find_one({"_id": result.inserted_id})
    return {"created": True, "device": serialize_id(created)}
