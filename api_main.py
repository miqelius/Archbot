from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from aiogram.types import Update

from bot import bot, dp 

from core.core_config import settings
from core.core_database import DatabaseManager, check_database_health
from core.core_redis import RedisClient
from celery_app import celery_app

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    try:
        logger.info("Initializing database...")
        DatabaseManager.initialize()
        if settings.environment == "development":
            await DatabaseManager.create_all_tables()
        
        health = await check_database_health()
        if not health:
            raise RuntimeError("Database health check failed")
        logger.info("✓ Database initialized")
        
        logger.info("Initializing Redis...")
        RedisClient.initialize()
        try:
            redis_health = await RedisClient.ping()
            if not redis_health:
                logger.warning("Bypassing Redis health check failure for local run")
        except Exception as e:
            logger.warning(f"Redis connection warning (bypassing for local run): {e}")
        logger.info("✓ Redis initialized")
        
        try:
            celery_app.connection().connect().close()
            logger.info("✓ Celery broker connected")
        except Exception as e:
            logger.warning(f"Celery broker warning: {e}")
            
        logger.info(f"✓ {settings.app_name} started successfully")
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
        
    yield
    
    logger.info("Shutting down...")
    try:
        await RedisClient.close()
    except Exception:
        pass
    logger.info("Shutdown complete")

def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    return application

app = create_app()

@app.get("/", tags=["Main"])
async def read_root():
    return {"message": "Welcome to Archbot API!"}

@app.post("/webhook", tags=["Telegram"])
async def telegram_webhook(update: dict):
    telegram_update = Update.model_validate(update, context={"bot": bot})
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}
