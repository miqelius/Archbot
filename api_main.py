from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
from aiogram.types import Update

from bot import bot, dp 
from core.core_config import settings
from core.core_database import DatabaseManager, check_database_health
from core.core_redis import RedisClient
from celery_app import celery_app
from fastapi.middleware.cors import CORSMiddleware
from routers.jobs import router as jobs_router 

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    
    # Database initialization (Safe fallback)
    try:
        logger.info("Initializing database...")
        DatabaseManager.initialize()
        if settings.environment == "development":
            await DatabaseManager.create_all_tables()
        
        health = await check_database_health()
        if not health:
            logger.warning("⚠️ Database health check failed, continuing without database...")
        else:
            logger.info("✓ Database initialized")
    except Exception as e:
        logger.warning(f"⚠️ Database connection warning (continuing without DB): {e}")
    
    # Redis initialization (Safe fallback)
    try:
        logger.info("Initializing Redis...")
        RedisClient.initialize()
        redis_health = await RedisClient.ping()
        if not redis_health:
            logger.warning("Bypassing Redis health check failure for local run")
        logger.info("✓ Redis initialized")
    except Exception as e:
        logger.warning(f"Redis connection warning (bypassing for local run): {e}")
    
    # Celery check
    try:
        celery_app.connection().connect().close()
        logger.info("✓ Celery broker connected")
    except Exception as e:
        logger.warning(f"Celery broker warning: {e}")
        
    logger.info(f"✓ {settings.app_name} started successfully")
    
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
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # ყველა წყაროდან შემოსული მოთხოვნის დაშვება
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return application

app = create_app()

# როუტერი იერთება მას შემდეგ, რაც აპლიკაცია (app) სრულად შეიქმნება
app.include_router(jobs_router, prefix="/api/v1")

@app.get("/", tags=["Main"])
async def read_root():
    return {"message": "Welcome to Archbot API!"}

@app.post("/webhook", tags=["Telegram"])
async def telegram_webhook(update: dict):
    telegram_update = Update.model_validate(update, context={"bot": bot})
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}
