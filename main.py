from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
from models import RealEstateListing
from services.gold_service import get_gold_market_price

def seed_initial_data():
    db = SessionLocal()
    try:
        if db.query(RealEstateListing).count() == 0:
            sample_listing = RealEstateListing(title="საბურთალო, 3 ოთახიანი ბინა", price=120000)
            db.add(sample_listing)
            db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_initial_data()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "system": "Archbot AI"}

@app.get("/api/greeting")
def get_greeting():
    return {
        "message": "Hello! I am Archbot AI, your intelligent market and real estate assistant. How can I help you today?"
    }

@app.get("/api/gold")
def get_gold():
    price = get_gold_market_price()
    return {"gold_price_oz": price}

@app.get("/api/listings")
def get_listings():
    db = SessionLocal()
    listings = db.query(RealEstateListing).all()
    db.close()
    return listings
