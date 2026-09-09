from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
from models import RealEstateListing
from services.market import get_market_data
from services.weather import get_tbilisi_weather
from services.ai_engine import evaluate_property

def seed_real_estate():
    db = SessionLocal()
    try:
        if db.query(RealEstateListing).count() == 0:
            sample_data = [
                {"title": "3-room apartment in Saburtalo", "district": "Saburtalo", "price_usd": 128000, "area_m2": 82, "rooms": 3},
                {"title": "Modern flat in Vake", "district": "Vake", "price_usd": 195000, "area_m2": 95, "rooms": 3},
                {"title": "Compact flat in Didi Dighomi", "district": "Didi Dighomi", "price_usd": 58000, "area_m2": 55, "rooms": 2}
            ]
            for item in sample_data:
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
            db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_real_estate()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/market")
def api_market():
    return get_market_data()

@app.get("/api/weather")
def api_weather():
    return get_tbilisi_weather()

@app.get("/api/system/status")
def api_system_status():
    return {
        "api_core": "Operational",
        "database": "Operational",
        "market_api": "Operational",
        "weather_api": "Operational",
        "property_scraper": "Operational",
        "celery_worker": "Operational"
    }

@app.get("/api/listings")
def get_listings():
    db = SessionLocal()
    listings = db.query(RealEstateListing).all()
    db.close()
    return listings
