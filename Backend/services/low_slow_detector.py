from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError


async def calculate_low_slow_score(db: AsyncIOMotorDatabase, user_id: str) -> tuple[int, list[str]]:
    reasons: list[str] = []

    try:
        rows = await (
            db.user_weekly_stats.find({"user_id": user_id})
            .sort("week_start", -1)
            .limit(4)
            .to_list(length=4)
        )
    except PyMongoError:
        return 0, ["Low-and-slow check unavailable due to database error"]

    if len(rows) < 4:
        return 0, reasons

    rows = list(reversed(rows))
    growth_count = 0

    for i in range(1, len(rows)):
        prev = float(rows[i - 1].get("avg_amount", 0.0))
        curr = float(rows[i].get("avg_amount", 0.0))
        if prev <= 0:
            continue
        if curr >= prev * 1.2:
            growth_count += 1

    if growth_count >= 3:
        reasons.append("Low-and-slow pattern: weekly average grew 20%+ for 3 consecutive weeks")
        return 85, reasons

    if growth_count == 2:
        reasons.append("Possible low-and-slow drift in weekly transaction amount")
        return 45, reasons

    return 0, reasons
