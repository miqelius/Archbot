"""
MatchMind AI — Background Task Scheduler
APScheduler setup for automatic daily prediction refreshes
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
import asyncio

from app.core.database import AsyncSessionLocal
from api_integration import MatchPredictionPipeline, FOOTBALL_DATA_TOKEN

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


# === Scheduled Jobs ===

async def daily_prediction_refresh():
    """
    Daily job: Fetch all today's matches and pre-calculate predictions.
    Runs at 06:00 UTC (early morning for European leagues).
    """
    logger.info("Starting daily prediction refresh...")
    async with AsyncSessionLocal() as db:
        try:
            pipeline = MatchPredictionPipeline(FOOTBALL_DATA_TOKEN)
            await pipeline.process_todays_matches(db)
            logger.info("Daily refresh completed successfully")
        except Exception as e:
            logger.error(f"Daily refresh failed: {e}")


async def hourly_live_update():
    """
    Hourly job: Update live match statistics and re-calculate live predictions.
    Runs every hour to catch real-time goal updates, possession changes, etc.
    """
    logger.info("Starting hourly live update...")
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import select
            from models import Match
            from datetime import datetime, timedelta
            
            # Get currently live matches
            now = datetime.utcnow()
            one_day_ago = now - timedelta(days=1)
            
            stmt = select(Match).where(
                (Match.status == "live") | 
                ((Match.match_date >= one_day_ago) & (Match.match_date <= now))
            )
            result = await db.execute(stmt)
            live_matches = result.scalars().all()
            
            logger.info(f"Updating {len(live_matches)} live/recent matches")
            
            # Update each match with latest stats
            pipeline = MatchPredictionPipeline(FOOTBALL_DATA_TOKEN)
            await pipeline.api_client.init_session()
            
            try:
                for match in live_matches:
                    # Fetch latest match data from API
                    match_data = await pipeline.api_client.session.get(
                        f"{pipeline.api_client.base_url}/matches/{match.external_id}",
                        headers=pipeline.api_client.headers,
                        timeout=10
                    )
                    
                    if match_data.status == 200:
                        data = await match_data.json()
                        match_info = data.get("match", {})
                        
                        # Update match statistics
                        match.status = match_info.get("status", match.status)
                        match.home_goals = match_info.get("score", {}).get("fullTime", {}).get("home")
                        match.away_goals = match_info.get("score", {}).get("fullTime", {}).get("away")
                        match.home_possession = match_info.get("possession", {}).get("home")
                        match.away_possession = match_info.get("possession", {}).get("away")
                        match.updated_at = datetime.utcnow()
                
                await db.commit()
                logger.info("Hourly update completed")
            finally:
                await pipeline.api_client.close_session()
        
        except Exception as e:
            logger.error(f"Hourly update failed: {e}")


async def weekly_team_stats_update():
    """
    Weekly job: Recalculate team statistics and xG averages.
    Runs every Monday at 00:00 UTC.
    """
    logger.info("Starting weekly team stats update...")
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import select, func
            from models import Team, Match
            
            stmt = select(Team)
            result = await db.execute(stmt)
            teams = result.scalars().all()
            
            for team in teams:
                # Calculate recent xG stats
                from api_integration import xGEstimationEngine
                xg_for, xg_against = await xGEstimationEngine.calculate_team_xg(db, team.id)
                
                team.avg_xg_for = xg_for
                team.avg_xg_against = xg_against
                team.last_updated = datetime.utcnow()
            
            await db.commit()
            logger.info(f"Updated stats for {len(teams)} teams")
        
        except Exception as e:
            logger.error(f"Weekly team stats update failed: {e}")


# === Scheduler Configuration ===

def configure_scheduler(app):
    """
    Attach scheduler to FastAPI app lifecycle.
    Call this in main.py startup event.
    """
    
    # Daily refresh at 06:00 UTC
    scheduler.add_job(
        daily_prediction_refresh,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="daily_refresh",
        name="Daily Prediction Refresh",
        replace_existing=True
    )
    
    # Hourly live updates
    scheduler.add_job(
        hourly_live_update,
        trigger=IntervalTrigger(hours=1),
        id="hourly_update",
        name="Hourly Live Match Update",
        replace_existing=True
    )
    
    # Weekly team stats update (Monday at 00:00)
    scheduler.add_job(
        weekly_team_stats_update,
        trigger=CronTrigger(day_of_week=0, hour=0, minute=0, timezone="UTC"),
        id="weekly_stats",
        name="Weekly Team Stats Update",
        replace_existing=True
    )
    
    logger.info("Scheduler configured with 3 jobs")


async def start_scheduler():
    """Start the scheduler"""
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")


async def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped")
