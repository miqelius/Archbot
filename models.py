from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from database import Base

class RealEstateListing(Base):
    __tablename__ = "real_estate_listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    district = Column(String, index=True)
    price_usd = Column(Float)
    area_m2 = Column(Float)
    rooms = Column(Integer)
    price_per_m2 = Column(Float)
    ai_score = Column(Integer)
    ai_verdict = Column(String)
    url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
