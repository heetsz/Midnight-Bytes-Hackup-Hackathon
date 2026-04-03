def make_decision(risk_score: int) -> str:
    if risk_score > 80:
        return "BLOCK"
    if 50 <= risk_score <= 80:
        return "MFA"
    return "APPROVE"
