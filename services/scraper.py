from sqlalchemy.orm import Session
from models import RealEstateListing
from services.ai_engine import evaluate_property

def run_property_scraper(db: Session):
    new_data = [
        {"title": "Renovated 2-room flat in Vake", "district": "Vake", "price_usd": 145000, "area_m2": 70, "rooms": 2},
        {"title": "Studio apartment in Gldani", "district": "Gldani", "price_usd": 42000, "area_m2": 40, "rooms": 1}
    ]
    indexed = 0
    skipped = 0

    for item in new_data:
        exists = db.query(RealEstateListing).filter(RealEstateListing.title == item["title"]).first()
        if not exists:
            eval_res = evaluate_property(item["district"], item["price_usd"], item["area_m2"])
            listing = RealEstateListing(
                title=item["title"],
                district=item["district"],
                price_usd=item["price_usd"],
                area_m2=item["area_m2"],
                rooms=item["rooms"],
                price_per_m2=eval_res["price_per_m2"],
                ai_score=eval_res["ai_score"],
                ai_verdict=eval_res["ai_verdict"]
            )
            db.add(listing)
            indexed += 1
        else:
            skipped += 1

    db.commit()
    return {
        "status": "completed",
        "listings_indexed": indexed,
        "duplicates_skipped": skipped,
        "failed_requests": 0
    }
