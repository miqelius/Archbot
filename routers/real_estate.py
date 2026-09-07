from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import RealEstate

router = APIRouter(prefix="/api/real-estate", tags=["Real Estate"])

@router.get("/search")
async def search_properties(city: str = None, max_price: float = None, db: Session = Depends(get_db)):
    query = db.query(RealEstate)
    if city:
        query = query.filter(RealEstate.location.ilike(f"%{city}%"))
    if max_price:
        query = query.filter(RealEstate.price <= max_price)
    return query.all()
