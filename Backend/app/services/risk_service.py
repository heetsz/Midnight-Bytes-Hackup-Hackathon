def calculate_risk_score(anomalies: dict[str, bool]) -> int:
    score = 0

    if anomalies.get("amount_above_average"):
        score += 35
    if anomalies.get("new_location"):
        score += 20
    if anomalies.get("new_device"):
        score += 20
    if anomalies.get("unusual_time"):
        score += 15

    return min(score, 100)
