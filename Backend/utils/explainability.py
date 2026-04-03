def merge_explanations(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []

    for group in groups:
        for reason in group:
            if reason not in seen:
                seen.add(reason)
                merged.append(reason)

    return merged


def get_risk_level(score: int) -> str:
    if score >= 81:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 41:
        return "MEDIUM"
    return "LOW"
