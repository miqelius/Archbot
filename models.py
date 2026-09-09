from sqlalchemy import Column, Integer, String, Float
from database import Base

class RealEstateListing(Base):
    __tablename__ = "real_estate_listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    price = Column(Float)
