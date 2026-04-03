from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError


async def calculate_ring_score(db: AsyncIOMotorDatabase, user_id: str) -> tuple[int, list[str], float]:
    try:
        link = await db.fraud_ring_links.find_one({"user_id": user_id}, sort=[("confidence", -1)])
    except PyMongoError:
        return 0, ["Fraud ring check unavailable due to database error"], 0.0

    if not link:
        return 0, [], 0.0

    confidence = float(link.get("confidence", 0.0))
    if confidence > 0.8:
        return 100, [f"Fraud ring link detected with confidence {confidence:.2f}"], confidence

    return 0, [], confidence
