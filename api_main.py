import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers.automation import router as automation_router
from routers.copilot import router as copilot_router
from routers.market import router as market_router
from routers.real_estate import router as real_estate_router
from routers.sports import router as sports_router, update_sports_data_periodically
from routers.weather import router as weather_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(update_sports_data_periodically())
    print("✅ [MatchMind] ფონური მუშა გაშვებულია")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("🛑 [MatchMind] ფონური მუშა გაჩერდა")

app = FastAPI(title="Archbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# სტატიკური ფაილების საქაღალდის მიბმა (თუ არსებობს)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return {"status": "operational", "service": "Archbot API"}

@app.get("/app")
async def serve_dashboard():
    # ვამოწმებთ სხვადასხვა შესაძლო ადგილს, სოფო/ფრონტენდის მთავარი ფაილი სად შეიძლება იყოს
    for path in ["static/index.html", "index.html", "public/index.html"]:
        if os.path.exists(path):
            return FileResponse(path)
    return {"status": "success", "message": "API და ფონური მუშა მუშაობს. მოათავსეთ index.html static/ საქაღალდეში."}

# როუტერების ინტეგრაცია
app.include_router(sports_router, prefix="/api/sports", tags=["Sports"])
app.include_router(market_router, prefix="/api/market", tags=["Market"])
app.include_router(real_estate_router, prefix="/api/listings", tags=["Listings"])
app.include_router(weather_router, prefix="/api/weather", tags=["Weather"])
app.include_router(copilot_router, prefix="/api/copilot", tags=["Copilot"])
app.include_router(automation_router, prefix="/api/automation", tags=["Automation"])
