from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
from models import RealEstateListing
from services.market import get_market_data
from services.weather import get_tbilisi_weather

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
