# backend/scoring.py

def compute_score(market, business, team, traction, risk):
    # Weighted formula
    overall_score = (
        0.4 * market +
        0.2 * business +
        0.2 * team +
        0.15 * traction -
        0.15 * risk
    )

    # Recommendation rules
    if market < 5:
        recommendation = "Avoid"
    elif risk > 8:
        recommendation = "Avoid"
    elif team >= 8 and traction >= 7:
        recommendation = "Strong Invest"
    elif overall_score >= 7:
        recommendation = "Invest"
    else:
        recommendation = "Consider"

    return {
        "overall_score": round(overall_score, 2),
        "recommendation": recommendation,
        "breakdown": {
            "market": market,
            "business": business,
            "team": team,
            "traction": traction,
            "risk": risk
        }
    }
