((
‘MatchMind EI Hub API â€ -v2.1
Updated with database persistence, live data integration, and cached predictions
)`

from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSessio
from sqlalchemy import select, and_
from datetime import datetime, teltadeta
from typing import List, Optional
import logging

from app.core.database import AsyncSessionLocal, engine, Base
from app.engines.poisson_engine import calculate_match_probabilities
from app.engines.agents import ConsensusEngine
import Match, Team, Prediction
from api_integration import MatchPredictionPipeline, FOOTBALL^DATA_TOKEN

logging = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(    title="MatchMind AI Hub API",    version="2.1.0",    description="Professional football match prediction engine with live data integration")

consensus_engine = ConsensusEngine()


# === pydantic Models ===

class MatchPredictionRequest(BaseModel):    """Request model for manual prediction (backward compatible)""_    home_team: str = Field(..., example="Arsenal")    away_team: str = Field(..., example="Chelsea")    home_xg: float = field(..., ge=0.0, le=10.0, example=1.85)    away_xg: float = Field(..., ge=0.0, le=10.0, example=1.10)    home_form: str = Field(default="N/A", example="W-W-D-W-L")    away_form: str = Field(default="N/A", example="L-D-W-W-L")    home_formation: str = Field(default="N/A", example="4-3-3")    away_formation: str = Field(default="N/A", example="4-4-2")


class MatchPredictionResponse(BaseModel):    """Unified response model"""    id: int    match_date: datetime    teams: dict    league: Optional[str]    status: str    # Calculated statistics    home_xg: Optional[float]    away_xg: Optional[float]    # Probabilities    probabilities: dict    ai_consensus: Optional[dic|]    confidence_score: Optional[float]    class Config:        from_attributes = True


class MatchListResponse(BaseModel):    """List of upcoming matches with predictions"""    count: int    next_update: datetime    matches: List[MatchPredictionResponse]


# === Dependency: Database Session ===

async def get_db():    async with AsyncSessionLocal() as session:        yield session


# === API Endpoints ===

@app.on_event("startup")
async def startup():    """Initialize database tables"""    async with engine.begin() as conn:        awain conn.run_sync(Base.metadata.create_all)    logger.info("Database initialized")


@)…ÁÀ¹•Ð ˆ½…Á¤½¡•…±Ñ ˆ¤)…Íå¹Œ‘•˜¡•…±Ñ¡}¡•¬ ¤è€€€É•ÑÕÉ¸ì€€€€€€€€‰ÍÑ…ÑÕÌˆè€‰¡•…±Ñ¡¤ˆ°€€€€€€€€‰Í•ÉÙ¥”ˆè€‰5…Ñ¡5¥¹$	…­•¹ˆ°€€€€€€€€‰Ù•ÉÍ¥½¸ˆè€ˆÈ¸Ä¸Àˆ°€€€€€€€€‰‘…Ñ…}Í½ÕÉ”ˆè€‰½½Ñ‰…±°µ…Ñ„¹½Éœ€¬1¥Ù”UÁ‘…Ñ•Ìˆ€€€ô(()…ÁÀ¹Á½ÍÐ ˆ½…Á¤½ÁÉ•‘¥Ðˆ¤)…Íå¹Œ‘•˜ÁÉ•‘¥Ñ}µ…Ñ ¤€€€‘…Ñ„è5…Ñ¡AÉ•‘¥Ñ¥½¹I•ÅÕ•ÍÐ°€€€‘ˆèÍå¹M•ÍÍ¥½¸€ô•Á•¹‘Ì¡•Ñ}‘ˆ¤¤è€€€€ˆˆˆ€€€5…¹Õ…°ÁÉ•‘¥Ñ¥½¸•¹‘Á½¥¹Ð€¡‰…­Ý…É½µÁ…Ñ¥‰±”¤¸€€€•ÁÑÌá€¬Ñ•…´‘…Ñ„…¹É•ÑÕÉ¹ÌA½¥ÍÍ½¸ÁÉ½‰…‰¥±¥Ñ¥•Ì€¬$½¹Í•¹ÍÕÌ¸€€€€€€€UÍ”™½ÈÕÍÑ½´Í•¹…É¥½È½È…µ¡½ŒÁÉ•‘¥Ñ¥½¹Ì¸€€€¼ˆˆˆ€€€ÑÉäè€€€€€€€ÁÉ½‰…‰¥±¥Ñ¥•Ì€ô…±Õ±…Ñ•}µ…Ñ¡}ÁÉ½‰…‰¥±¥Ñ¥•Ì¡‘…Ñ„¹¡½µ•}áœ°‘…Ñ„¹…Ý…å}áœ¤€€€€€€€€€€€µ…Ñ¡}‘¥Ð€ô‘…Ñ„¹‘¥Ð ¤€€€€€€€…¥}…¹…±åÍ¥Ì€ô½¹Í•¹ÍÕÍ}•¹¥¹”¹•Ù…±Õ…Ñ”¡µ…Ñ¡}‘¥Ð¤€€€€€€€€€€€É•ÑÕÉ¸ì€€€€€€€€€€€€‰Ñ•…µÌˆè€Á¤€€€€€€€€€€€€€€€€‰¡½µ”ˆè‘…Ñ„¹¡½µ•}Ñ•…´°€€€€€€€€€€€€€€€€‰…Ý…äˆè‘…Ñ„¹…Ý…å}Ñ•…´€€€€€€€€€€€ô°€€€€€€€€€€€€‰ÁÉ½‰…‰¥±¥Ñ¥•ÌˆèÁÉ½‰…‰¥±¥Ñ¥•Ì°€€€€€€€€€€€€‰…¥}½¹Í•¹ÍÕÌˆè…¥}…¹…±åÍ¥Ì°€€€€€€€€€€€€‰¹½Ñ”ˆè€‰5…¹Õ…°ÁÉ•‘¥Ñ¥½¸€¡¹½Ð…¡•¥¸‘…Ñ…‰…Í”¤ˆ€€€€€€€ô€€€•á•ÁÐá•ÁÑ¥½¸…Ì”è€˜É…¥Í”!QQAá•ÁÑ¥½¸¡ÍÑ…ÑÕÍ}½‘”ôÔÀÀ°‘•Ñ…¥°õÍÑÈ¡”¤¤((+–ƒš>§–B3¾ò0AÉ½•ÍÌ½µÁ±•Ñ•„