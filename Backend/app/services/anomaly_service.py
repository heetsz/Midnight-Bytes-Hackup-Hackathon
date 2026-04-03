from typing import Any

from app.models.schemas import TransactionRequest


# Detect behavior anomalies compared with user's historical profile.
def detect_anomalies(profile: dict[str, Any], payload: TransactionRequest) -> dict[str, bool]:
    avg_amount = float(profile.get("avg_amount", 0.0))
    total_transactions = int(profile.get("total_transactions", 0))

    known_locations = set(profile.get("locations", []))
    known_devices = set(profile.get("devices", []))

    amount_above_average = total_transactions > 0 and payload.amount > avg_amount
    new_location = payload.location not in known_locations
    new_device = payload.device not in known_devices

    hour_activity = profile.get("hour_activity", {})
    current_hour = str(payload.timestamp.hour)
    unusual_time = False

    # Time anomaly only after enough data points exist.
    if total_transactions >= 5 and hour_activity:
        sorted_hours = sorted(hour_activity.items(), key=lambda item: item[1], reverse=True)
        common_hours = {hour for hour, _ in sorted_hours[:3]}
        unusual_time = current_hour not in common_hours

    return {
        "amount_above_average": amount_above_average,
        "new_location": new_location,
        "new_device": new_device,
        "unusual_time": unusual_time,
    }
