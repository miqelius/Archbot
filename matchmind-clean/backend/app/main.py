from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.engines.poisson_engine import calculate_match_probabilities
from app.engines.agents import ConsensusEngine

app = FastAPI(
    title="MatchMind AI Hub API",
    version="2.0.0",
    description="Professional football match prediction engine powered by Poisson distribution and multi-agent AI analysis."
)

consensus_engine = ConsensusEngine()

class MatchPredictionRequest(BaseModel):
    home_team: str = Field(..., example="Arsenal")
    away_team: str = Field(..., example="Chelsea")
    home_xg: float = Field(..., ge=0.0, le=10.0, example=1.85)
    away_xg: float = Field(..., ge=0.0, le=10.0, example=1.10)
    home_form: str = Field(default="W-W-D-W-L", example="W-W-D-W-L")
    away_form: str = Field(default="L-D-W-W-L", example="L-D-W-W-L")
    home_formation: str = Field(default="4-3-3", example="4-3-3")
    away_formation: str = Field(default="4-4-2", example="4-4-2")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "MatchMind AI Backend", "version": "2.0.0"}

@app.post("/api/predict")
async def predict_match(data: MatchPredictionRequest):
    try:
        # 1. Calculate statistical probabilities using Poisson model
        probabilities = calculate_match_probabilities(data.home_xg, data.away_xg)
        
        # 2. Run multi-agent AI analysis (Stats, Form, Tactical)
        match_data_dict = data.dict()
        ai_analysis = consensus_engine.evaluate(match_data_dict)
        
        return {
            "teams": {
                "home": data.home_team,
                "away": data.away_team
            },
            "probabilities": probabilities,
            "ai_consensus": ai_analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
