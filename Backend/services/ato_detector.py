from datetime import datetime

from models.schemas import TransactionAnalyzeRequest


def calculate_ato_score(user: dict, payload: TransactionAnalyzeRequest, now: datetime) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    trusted_devices = set(user.get("trusted_devices", []))
    usual_cities = set(user.get("usual_cities", []))
    usual_login_hour = int(user.get("usual_login_hour", 12))

    if payload.device_fingerprint not in trusted_devices:
        score += 40
        reasons.append("Unknown device detected")

    if payload.city not in usual_cities:
        score += 35
        reasons.append(f"Transaction from new city: {payload.city}")

    hour = now.hour
    if abs(hour - usual_login_hour) >= 6:
        score += 25
        reasons.append(f"Unusual hour: {hour}:00")

    return min(score, 100), reasons
