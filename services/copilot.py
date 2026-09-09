from sqlalchemy.orm import Session
from models import RealEstateListing

def process_copilot_query(query: str, db: Session):
    query_lower = query.lower()

    if "under" in query_lower or "150k" in query_lower:
        listings = db.query(RealEstateListing).filter(RealEstateListing.price_usd <= 150000).all()
        return {
            "type": "property_search",
            "message": f"Found {len(listings)} properties under $150,000.",
            "data": [
                {
                    "title": l.title,
                    "district": l.district,
                    "price_usd": l.price_usd,
                    "price_per_m2": l.price_per_m2,
                    "ai_score": l.ai_score,
                    "ai_verdict": l.ai_verdict
                } for l in listings
            ]
        }
    elif "compare" in query_lower or "vake" in query_lower:
        return {
            "type": "comparison",
            "message": "District Benchmark Comparison (USD / m²):",
            "data": {
                "Vake": {"avg_m2": 1800.0, "demand": "High", "roi_estimate": "5.8%"},
                "Saburtalo": {"avg_m2": 1400.0, "demand": "Very High", "roi_estimate": "6.9%"}
            }
        }
    else:
        return {
            "type": "general",
            "message": f"Archbot Copilot Analysis: Query processed. Market trend is stable with high liquidity in residential sectors.",
            "data": None
        }
