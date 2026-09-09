DISTRICT_BENCHMARKS = {
    "vake": 1800.0,
    "saburtalo": 1400.0,
    "didi dighomi": 900.0,
    "gldani": 850.0,
    "center": 2100.0
}

def evaluate_property(district: str, price_usd: float, area_m2: float):
    if area_m2 <= 0:
        return {"price_per_m2": 0.0, "ai_score": 50, "ai_verdict": "Neutral"}

    price_per_m2 = round(price_usd / area_m2, 2)
    benchmark = DISTRICT_BENCHMARKS.get(district.lower().strip(), 1300.0)
    diff_percentage = ((benchmark - price_per_m2) / benchmark) * 100

    base_score = 70 + int(diff_percentage)
    ai_score = max(10, min(99, base_score))

    if diff_percentage >= 7.0:
        ai_verdict = "Good deal"
    elif diff_percentage <= -10.0:
        ai_verdict = "Overpriced"
    else:
        ai_verdict = "Fair market value"

    return {
        "price_per_m2": price_per_m2,
        "ai_score": ai_score,
        "ai_verdict": ai_verdict,
        "diff_percentage": round(diff_percentage, 1)
    }
