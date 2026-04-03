def generate_reasons(anomalies: dict[str, bool], risk_score: int) -> list[str]:
    reasons: list[str] = []

    if anomalies.get("amount_above_average"):
        reasons.append("Transaction amount is above user average")
    if anomalies.get("new_location"):
        reasons.append("Transaction location is new for this user")
    if anomalies.get("new_device"):
        reasons.append("Transaction device is new for this user")
    if anomalies.get("unusual_time"):
        reasons.append("Transaction time is unusual for this user")

    if not reasons:
        reasons.append("No strong anomaly signal detected")

    if risk_score > 80:
        reasons.append("Risk score crossed BLOCK threshold")
    elif risk_score >= 50:
        reasons.append("Risk score crossed MFA threshold")
    else:
        reasons.append("Risk score is in APPROVE range")

    return reasons
