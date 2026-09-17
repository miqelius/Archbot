"""
MatchMind AI — Football-Data.org Integration
Fetches live matches, team stats, and updates prediction cache
"""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from models import Match, Team, Prediction, TeamFormHistory, APICacheLog
from engines.poisson_engine import calculate_match_probabilities
from engines.agents import ConsensusEngine

logger = logging.getLogger(__name__)

FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
FOOTBALL_DATA_TOKEN = "YOUR_FOOTBALL_DATA_ORG_TOKEN"

MATCH_CACHE_EXPIRY = 24
TEAM_STATS_CACHE_EXPIRY = 6

class FootballDataAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = FOOTBALL_DATA_BASE_URL
        self.headers = {"X-Auth-Token": api_key}
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_request_time = None
        self.request_interval = 0.1

    async def init_session(self):
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def _rate_limit_wait(self):
        if self.last_request_time:
            elapsed = (datetime.utcnow() - self.last_request_time).total_seconds()
            if elapsed < self.request_interval:
                await asyncio.sleep(self.request_interval - elapsed)
        self.last_request_time = datetime.utcnow()

    async def get_matches_today(self, db: AsyncSession) -> List[Dict]:
        await self._rate_limit_wait()
        await self._log_api_call(db, "football-data", "/matches", "upcoming")
        try:
            url = f"{self.base_url}/matches?status=SCHEDULED&competitions=PL,LA,SA,BL1,FL1"
            async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("matches", [])
                else:
                    logger.error(f"Football-Data API error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch matches: {e}")
            return []

    async def fetch_team_stats(self, team_id: int, season: int = 2024) -> Dict:
        await self._rate_limit_wait()
        try:
            url = f"{self.base_url}/teams/{team_id}"
            async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {}
        except Exception as e:
            logger.error(f"Failed to fetch team stats for team {team_id}: {e}")
            return {}

    async def _log_api_call(self, db: AsyncSession, provider: str, endpoint: str, status: str):
        try:
            cache_log = APICacheLog(
                api_provider=provider,
                endpoint=endpoint,
                response_status=200,
                called_at=datetime.utcnow()
            )
            db.add(cache_log)
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log API call: {e}")

class xGEstimationEngine:
    @staticmethod
    async def calculate_team_xg(db: AsyncSession, team_id: int) -> tuple[float, float]:
        stmt = select(Match).where(
            ((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
        ).order_by(Match.match_date.desc()).limit(10)
        
        result = await db.execute(stmt)
        recent_matches = result.scalars().all()
        
        if not recent_matches:
            return 1.5, 1.4
        
        total_shots = 0
        total_shots_against = 0
        matches_count = len(recent_matches)
        
        for match in recent_matches:
            is_home = match.home_team_id == team_id
            shots = match.home_shots if is_home else match.away_shots
            shots_against = match.away_shots if is_home else match.home_shots
            if shots:
                total_shots += shots
            if shots_against:
                total_shots_against += shots_against
        
        xg_for = (total_shots / matches_count) * 0.12 if total_shots > 0 else 1.5
        xg_against = (total_shots_against / matches_count) * 0.12 if total_shots_against > 0 else 1.4
        
        xg_for = min(max(xg_for, 0.5), 3.5)
        xg_against = min(max(xg_against, 0.5), 3.5)
        
        return round(xg_for, 2), round(xg_against, 2)

class MatchPredictionPipeline:
    def __init__(self, api_key: str):
        self.api_client = FootballDataAPIClient(api_key)
        self.xg_engine = xGEstimationEngine()
        self.consensus_engine = ConsensusEngine()

    async def process_todays_matches(self, db: AsyncSession):
        logger.info("Starting daily match prediction pipeline...")
        await self.api_client.init_session()
        try:
            matches_data = await self.api_client.get_matches_today(db)
            logger.info(f"Fetched {len(matches_data)} matches for today")
            for match_data in matches_data:
                await self._process_single_match(db, match_data)
            logger.info("Daily prediction pipeline completed")
        finally:
            await self.api_client.close_session()

    async def _process_single_match(self, db: AsyncSession, match_data: Dict):
        try:
            home_team_id = match_data["homeTeam"]["id"]
            away_team_id = match_data["awayTeam"]["id"]
            match_date = datetime.fromisoformat(match_data["utcDate"].replace("Z", "+00:00"))
            
            home_team = await self._upsert_team(db, match_data["homeTeam"])
            away_team = await self._upsert_team(db, match_data["awayTeam"])
            
            stmt = select(Match).where(Match.external_id == match_data["id"])
            result = await db.execute(stmt)
            existing_match = result.scalar()
            
            if existing_match:
                return
            
            home_xg, home_xg_against = await self.xg_engine.calculate_team_xg(db, home_team.id)
            away_xg, away_xg_against = await self.xg_engine.calculate_team_xg(db, away_team.id)
            
            match = Match(
                external_id=match_data["id"],
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                match_date=match_date,
                status="scheduled",
                league=match_data["competition"]["name"],
                season=match_data["season"]["currentSeason"],
                home_xg=home_xg,
                away_xg=away_xg,
                venue=match_data.get("venue", "")
            )
            db.add(match)
            await db.flush()
            
            probabilities = calculate_match_probabilities(home_xg, away_xg)
            
            ai_analysis = self.consensus_engine.evaluate({
                "home_team": home_team.name,
                "away_team": away_team.name,
                "home_xg": home_xg,
                "away_xg": away_xg,
                "home_form": "N/A",
                "away_form": "N/A",
                "home_formation": "N/A",
                "away_formation": "N/A"
            })
            
            prediction = Prediction(
                match_id=match.id,
                home_win_prob=probabilities["home_win_prob"],
                draw_prob=probabilities["draw_prob"],
                away_win_prob=probabilities["away_win_prob"],
                over_2_5_prob=probabilities["over_2.5_prob"],
                btts_prob=probabilities["btts_prob"],
                ai_consensus=ai_analysis,
                calculated_at=datetime.utcnow()
            )
            db.add(prediction)
            await db.commit()
            logger.info(f"Processed match: {home_team.name} vs {away_team.name}")
        except Exception as e:
            logger.error(f"Error processing match {match_data.get(id)}: {e}")
            await db.rollback()

    async def _upsert_team(self, db: AsyncSession, team_data: Dict) -> Team:
        stmt = select(Team).where(Team.external_id == team_data["id"])
        result = await db.execute(stmt)
        team = result.scalar()
        if team:
            return team
        team = Team(
            external_id=team_data["id"],
            name=team_data["name"],
            country=team_data.get("area", {}).get("name"),
            logo_url=team_data.get("crest"),
            last_updated=datetime.utcnow()
        )
        db.add(team)
        await db.flush()
        return team

async def run_daily_prediction_job():
    async with AsyncSessionLocal() as db:
        pipeline = MatchPredictionPipeline(FOOTBALL_DATA_TOKEN)
        await pipeline.process_todays_matches(db)

if __name__ == "__main__":
    asyncio.run(run_daily_prediction_job())
