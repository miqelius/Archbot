from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.models import RealEstateListing

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
    return {"status": "online", "system": "Archbot API"}
