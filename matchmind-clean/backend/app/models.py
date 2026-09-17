from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(Integer, unique=True, index=True)  # ID from Football-Data.org
    name = Column(String(100), unique=True, index=True)
    country = Column(String(100), nullable=True)
    logo_url = Column(String(255), nullable=True)
    
    # Statistics summary
    matches_played = Column(Integer, default=0)
    home_scored_avg = Column(Float, default=0.0)
    home_conceded_avg = Column(Float, default=0.0)
    away_scored_avg = Column(Float, default=0.0)
    away_conceded_avg = Column(Float, default=0.0)
    
    goals_scored_last_5 = Column(Integer, default=0)
    goals_conceded_last_5 = Column(Integer, default=0)
    home_form = Column(String(100), nullable=True)
    away_form = Column(String(100), nullable=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(Integer, unique=True, index=True)
    league_code = Column(String(20), index=True)  # PL, LA, SA, etc.
    home_team = Column(String(100), index=True)
    away_team = Column(String(100), index=True)
    match_date = Column(DateTime, index=True)
    status = Column(String(50), default="SCHEDULED")  # SCHEDULED, LIVE, FINISHED
    
    # Score
    home_goals = Column(Integer, nullable=True)
    away_goals = Column(Integer, nullable=True)
    
    # Predictions & xG
    home_xg = Column(Float, nullable=True)
    away_xg = Column(Float, nullable=True)
    home_win_prob = Column(Float, nullable=True)
    draw_prob = Column(Float, nullable=True)
    away_win_prob = Column(Float, nullable=True)
    over_25_prob = Column(Float, nullable=True)
    btts_prob = Column(Float, nullable=True)
    ai_consensus = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class APICacheLog(Base):
    __tablename__ = "api_cache_log"
    
    id = Column(Integer, primary_key=True, index=True)
    api_provider = Column(String(50))
    endpoint = Column(String(255))
    response_status = Column(Integer)
    cached = Column(Boolean, default=False)
    called_at = Column(DateTime, default=datetime.utcnow)
    next_available_at = Column(DateTime, nullable=True)
