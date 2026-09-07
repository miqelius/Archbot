from sqlalchemy import Column, Integer, String, Text
from database import Base

class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="completed")
    result = Column(Text, nullable=True)

from sqlalchemy import Column, Integer, String, Float
from database import Base

class RealEstate(Base):
    __tablename__ = "real_estate"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    price = Column(Float)
    location = Column(String, index=True)
    rooms = Column(Integer)
    description = Column(String)
