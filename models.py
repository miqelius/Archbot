from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from database import Base

class RealEstateListing(Base):
    __tablename__ = "real_estate_listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    price = Column(Float, nullable=False)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Alias თავსებადობისთვის
RealEstate = RealEstateListing
